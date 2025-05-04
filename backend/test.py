import lgpio
import threading
import time

# BCM pin numbers
START_BUTTON_PIN = 16
CONVEYOR_RELAY_PIN = 23
CONVEYOR_RELAY_PIN2 = 24
CONVEYOR_RELAY_PIN3 = 25

chip = lgpio.gpiochip_open(0)

lgpio.gpio_claim_output(chip, CONVEYOR_RELAY_PIN)
lgpio.gpio_write(chip, CONVEYOR_RELAY_PIN, 0)

lgpio.gpio_claim_input(chip, START_BUTTON_PIN, lgpio.SET_PULL_UP)

def monitor_start_button():
    last_state = 1
    while True:
        state = lgpio.gpio_read(chip, START_BUTTON_PIN)
        if state == 0 and last_state == 1:
            lgpio.gpio_write(chip, CONVEYOR_RELAY_PIN, 1)
            print("Button pressed, starting conveyor...")
        elif state == 1 and last_state == 0:
            lgpio.gpio_write(chip, CONVEYOR_RELAY_PIN, 0)
            print("Button released, stopping conveyor...")
        last_state = state
        time.sleep(0.05)  # debounce delay

threading.Thread(target=monitor_start_button, daemon=True).start()

print("GPIO initialized. Waiting for button press...")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Exiting...")
    lgpio.gpiochip_close(chip)
