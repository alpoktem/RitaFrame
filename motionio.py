import RPi.GPIO as GPIO
import time, subprocess, os
import logging

class MotionDetector:
    def __init__(self, pir_pin, sleep_on_secs):
        self.pir_pin = pir_pin
        self.sleep_on_secs = sleep_on_secs
        # self.screen_on = True
        self.secs_since_last_activity = 0
        self.initialize_gpio()

    def initialize_gpio(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.pir_pin, GPIO.IN)

    def detect_motion(self):
        while True:
            motion_detected = GPIO.input(self.pir_pin)
            if motion_detected and self.secs_since_last_activity > 5:
                logging.info("Motion detected!")
                self.secs_since_last_activity = 0  # Reset the counter on motion detection
                # if not self.screen_on:
                self.wake_screen()
            elif motion_detected:
                self.secs_since_last_activity = 0  # Reset the counter on motion detection
            else:
                # if self.screen_on and self.secs_since_last_activity >= self.sleep_on_secs:
                if self.secs_since_last_activity >= self.sleep_on_secs:
                    # Only turn off the screen if it's on and the specified time has elapsed since last activity
                    self.sleep_screen()

            time.sleep(1)  # Adjust the sleep duration as needed
            self.secs_since_last_activity += 1

    def wake_screen(self):
        env = os.environ.copy()
        env['DISPLAY'] = ":0"
        try:
            subprocess.run(["xset", "dpms", "force", "on"], env=env, check=True)
            # self.screen_on = True
            logging.info("Screen waking up...")
        except subprocess.CalledProcessError as e:
            logging.error("Error waking up screen:", e)

    def sleep_screen(self):
        env = os.environ.copy()
        env['DISPLAY'] = ":0"
        try:
            subprocess.run(["xset", "dpms", "force", "off"], env=env, check=True)
            # self.screen_on = False
            logging.info("Screen turning off...")
        except subprocess.CalledProcessError as e:
            logging.error("Error turning off screen:", e)
