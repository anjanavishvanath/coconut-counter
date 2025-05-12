# simulate_gpio.py
import sys
import time
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'stubs'))

from RPi.GPIO import (  # Replace with your actual module name
    BCM, IN, OUT, PUD_UP, FALLING,
    setup, add_event_detect, _trigger
)

# ─── Setup GPIO (Mirror Your Backend's Configuration) ────────────────
def setup_hardware():
    setup(START_BUTTON_PIN, IN, pull_up_down=PUD_UP)
    setup(STOP_BUTTON_PIN, IN, pull_up_down=PUD_UP)
    add_event_detect(START_BUTTON_PIN, FALLING, callback=start_button_pressed, bouncetime=200)
    add_event_detect(STOP_BUTTON_PIN, FALLING, callback=stop_button_pressed, bouncetime=200)

# ─── Button Callbacks (Mirror Your Backend) ─────────────────────────
def start_button_pressed(channel):
    print("[TEST] Start button pressed (simulated)")

def stop_button_pressed(channel):
    print("[TEST] Stop button pressed (simulated)")

# ─── Interactive CLI ────────────────────────────────────────────────
if __name__ == "__main__":
    START_BUTTON_PIN = 16  # Match your backend's pin numbers
    STOP_BUTTON_PIN = 12

    setup_hardware()
    print("Simulation running. Press keys to trigger events:")
    print("  [A] Simulate START button press (pin 16)")
    print("  [S] Simulate STOP button press (pin 12)")
    print("  [Q] Quit")

    while True:
        key = input("> ").strip().lower()
        if key == 'a':
            _trigger(START_BUTTON_PIN)
        elif key == 's':
            _trigger(STOP_BUTTON_PIN)
        elif key == 'q':
            break
        else:
            print("Invalid key. Use A/S/Q.")