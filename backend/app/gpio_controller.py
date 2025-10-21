import sys
import os
# Add stubs/ to the front of module search path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'stubs')))
# Modules for GPIO manipulation in Raspberry Pi 
import RPi.GPIO as GPIO 
import lgpio
from .config import START_BUTTON_PIN, STOP_BUTTON_PIN, CONVEYOR_RELAY_PIN, BUZZER_PIN

class GPIOController:
    def __init__(self):
        self.chip = lgpio.gpiochip_open(0)  # Open the first GPIO chip
        # set outputs
        lgpio.gpio_claim_output(self.chip, CONVEYOR_RELAY_PIN)
        lgpio.gpio_claim_output(self.chip, BUZZER_PIN)
        #initialize outputs to low
        lgpio.gpio_write(self.chip, CONVEYOR_RELAY_PIN, 0)
        lgpio.gpio_write(self.chip, BUZZER_PIN, 0)
        # ─── RPi.GPIO setup for the button ────────────────────────────────────────
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(START_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(STOP_BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        # ─── Install a falling-edge interrupt with 200 ms debounce ─────────────────
        GPIO.add_event_detect(
            START_BUTTON_PIN,
            GPIO.FALLING,              # detect HIGH → LOW transitions
            callback=self._on_start_button_pressed,
            bouncetime=10             # debounce in milliseconds
        )

        GPIO.add_event_detect(
            STOP_BUTTON_PIN,
            GPIO.FALLING,              # detect HIGH → LOW transitions
            callback=self._on_stop_button_pressed,
            bouncetime=10             # debounce in milliseconds
        )

    def _on_start_button_pressed(self, channel):
        """Callback: button pressed → turn conveyor on."""
        print("Button pressed, starting conveyor…")
        if GPIO.input(START_BUTTON_PIN) == 0:
            if GPIO.input(START_BUTTON_PIN) == 0:
                lgpio.gpio_write(self.chip, CONVEYOR_RELAY_PIN, 1)
                lgpio.gpio_write(self.chip, BUZZER_PIN, 0)  # turn off buzzer

    def _on_stop_button_pressed(self, channel):
        print("Button pressed, stopping conveyor…")
        if GPIO.input(STOP_BUTTON_PIN) == 0:
            if GPIO.input(STOP_BUTTON_PIN) == 0:
                lgpio.gpio_write(self.chip, CONVEYOR_RELAY_PIN, 0)      

    def start_conveyor(self):
        """Start the conveyor by setting the relay pin high."""
        lgpio.gpio_write(self.chip, CONVEYOR_RELAY_PIN, 1)

    def stop_conveyor(self):
        """Stop the conveyor by setting the relay pin low."""
        lgpio.gpio_write(self.chip, CONVEYOR_RELAY_PIN, 0)

    def activate_buzzer(self):
        """Activate the buzzer by setting the pin high."""
        lgpio.gpio_write(self.chip, BUZZER_PIN, 1)

    def deactivate_buzzer(self):
        """Deactivate the buzzer by setting the pin low."""
        lgpio.gpio_write(self.chip, BUZZER_PIN, 0)

    def cleanup(self):
        """Clean up GPIO settings."""
        GPIO.cleanup()
        lgpio.gpiochip_close(self.chip) #see if needed