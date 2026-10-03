import time, subprocess, os
import logging
import threading

class MotionDetector:
    def __init__(self, pir_pin, sleep_on_secs):
        self.pir_pin = pir_pin
        self.sleep_on_secs = sleep_on_secs
        self.screen_on = True
        self.secs_since_last_activity = 0
        self.enabled = False
        self._stop = threading.Event()

    def initialize(self):
        # Imported lazily so this module stays importable on non-Pi machines.
        import RPi.GPIO as GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pir_pin, GPIO.IN)
        self._gpio = GPIO
        self.enabled = True

    def stop(self):
        self._stop.set()

    def detect_motion(self):
        GPIO = self._gpio
        while not self._stop.is_set():
            motion_detected = GPIO.input(self.pir_pin)
            if motion_detected and self.secs_since_last_activity > 5:
                logging.info("Motion detected!")
                self.secs_since_last_activity = 0  # Reset the counter on motion detection
                if not self.screen_on:
                    self.wake_screen()
            elif motion_detected:
                self.secs_since_last_activity = 0  # Reset the counter on motion detection
            else:
                if self.screen_on and self.secs_since_last_activity >= self.sleep_on_secs:
                    # Only turn off the screen if it's on and the specified time has elapsed since last activity
                    self.sleep_screen()

            time.sleep(1)  # Adjust the sleep duration as needed
            self.secs_since_last_activity += 1
        logging.info('Motion detection thread exiting')

    def wake_screen(self):
        env = os.environ.copy()
        env['DISPLAY'] = ":0"
        try:
            subprocess.run(["xset", "dpms", "force", "on"], env=env, check=True)
            self.screen_on = True
            logging.info("Screen waking up...")
        except subprocess.CalledProcessError as e:
            logging.error("Error waking up screen:", e)

    def sleep_screen(self):
        env = os.environ.copy()
        env['DISPLAY'] = ":0"
        try:
            subprocess.run(["xset", "dpms", "force", "off"], env=env, check=True)
            self.screen_on = False
            logging.info("Screen turning off...")
        except subprocess.CalledProcessError as e:
            logging.error("Error turning off screen:", e)

    def is_screen_on(self):
        """Check if the screen is currently on by parsing the output of `xset q`."""
        env = os.environ.copy()
        env['DISPLAY'] = ":0"
        try:
            result = subprocess.run(["xset", "q"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True)
            if "Monitor is On" in result.stdout:
                self.screen_on = True
                return True
            elif "Monitor is Off" in result.stdout:
                self.screen_on = False
                return False
            else:
                logging.warning("Could not determine the screen state from xset output.")
                return self.screen_on  
        except subprocess.CalledProcessError as e:
            logging.error("Failed to check screen state: %s", e)
            return self.screen_on  


class MotionController:
    """Starts the PIR detector when configured, and degrades to a no-op otherwise.

    Wrapping the detector keeps RPi.GPIO, xset and thread management out of the
    request path, and gives callers a safe is_screen_on() on any machine.
    """

    def __init__(self, config):
        self.config = config
        self.detector = None
        self.error = None

    @property
    def enabled(self):
        return bool(self.config.get('run_motion_detection', False))

    @property
    def running(self):
        return self.detector is not None and self.detector.enabled

    def start(self):
        if not self.enabled or self.running:
            return
        try:
            detector = MotionDetector(
                self.config.get('pir_pin', 17),
                self.config.get('sleep_on_secs', 500),
            )
            detector.initialize()
            thread = threading.Thread(target=detector.detect_motion, daemon=True)
            thread.start()
            self.detector = detector
            logging.info('Motion detection thread started (BCM %s, sleep after %ss)',
                         self.config.get('pir_pin'),
                         self.config.get('sleep_on_secs'))
        except Exception as e:
            self.error = str(e)
            self.detector = None
            logging.error('Motion detection unavailable: %s', e)

    def stop(self):
        if self.detector:
            self.detector.stop()
            self.detector = None

    def sync(self):
        """Reconcile against the current config.

        `enabled` reads config live, so it can change without a restart, but the
        detector thread can only be started once at boot. Without this, flipping
        run_motion_detection made /api/status report True while nothing was
        actually running.
        """
        if self.enabled:
            self.start()
        elif self.detector:
            self.stop()

    def is_screen_on(self):
        if not self.detector:
            return True
        try:
            return self.detector.is_screen_on()
        except Exception as e:
            logging.warning('Could not read screen state: %s', e)
            return True
