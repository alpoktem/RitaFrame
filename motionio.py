import time, subprocess, os
import logging
import threading

class MotionDetector:
    def __init__(self, pir_pin, sleep_on_secs, wake_debounce_samples=2):
        self.pir_pin = pir_pin
        self.sleep_on_secs = sleep_on_secs
        self.wake_debounce_samples = wake_debounce_samples
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

    def shutdown(self):
        """Release the GPIO pin so nothing else in the process keeps it claimed.

        RPi.GPIO leaves pins latched until cleanup, and a pin left held by this
        process makes an unrelated diagnostic read look like a dead sensor.
        """
        gpio = getattr(self, '_gpio', None)
        if gpio is None:
            return
        try:
            gpio.cleanup(self.pir_pin)
        except Exception as e:
            logging.warning('GPIO cleanup failed on pin %s: %s', self.pir_pin, e)
        self.enabled = False

    def detect_motion(self):
        GPIO = self._gpio
        consecutive_high = 0
        while not self._stop.is_set():
            motion_detected = GPIO.input(self.pir_pin)
            if motion_detected:
                consecutive_high += 1
                self.secs_since_last_activity = 0
                # Wake on motion itself, not on the first sample that happens to
                # follow a quiet stretch. The previous code gated the wake on
                # secs_since_last_activity > 5, but the very act of detecting
                # motion resets that counter, so regular movement held it at 0
                # and branch one never ran: the screen slept reliably and then
                # ignored the movement that should have woken it.
                if not self.screen_on and consecutive_high >= self.wake_debounce_samples:
                    logging.info("Motion detected while screen was off")
                    self.wake_screen()
            else:
                consecutive_high = 0
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

    @property
    def _settings(self):
        return (self.config.get('pir_pin', 17),
                self.config.get('sleep_on_secs', 500))

    def start(self):
        if not self.enabled or self.running:
            return
        try:
            pir_pin, sleep_on_secs = self._settings
            detector = MotionDetector(pir_pin, sleep_on_secs)
            detector.initialize()
            thread = threading.Thread(target=detector.detect_motion, daemon=True)
            thread.start()
            self.detector = detector
            logging.info('Motion detection thread started (BCM %s, sleep after %ss)',
                         pir_pin, sleep_on_secs)
        except Exception as e:
            self.error = str(e)
            self.detector = None
            logging.error('Motion detection unavailable: %s', e)

    def stop(self):
        if self.detector:
            self.detector.stop()
            self.detector.shutdown()
            self.detector = None

    def sync(self):
        """Reconcile against the current config.

        `enabled` reads config live, so it can change without a restart, but the
        detector thread can only be started once at boot. Without this, flipping
        run_motion_detection made /api/status report True while nothing was
        actually running.

        The detector also captures pir_pin and sleep_on_secs at construction, so
        editing either would otherwise need a restart. Recreating the thread is
        cheap and keeps the whole motion section live-reloadable, like the rest
        of config.yaml.
        """
        if not self.enabled:
            if self.detector:
                self.stop()
            return

        if self.detector:
            if self._settings != (self.detector.pir_pin, self.detector.sleep_on_secs):
                logging.info('Motion settings changed, restarting detector')
                self.stop()

        self.start()

    def is_screen_on(self):
        if not self.detector:
            return True
        try:
            return self.detector.is_screen_on()
        except Exception as e:
            logging.warning('Could not read screen state: %s', e)
            return True
