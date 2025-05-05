import lgpio
import threading
import time

# BCM pin numbers
START_BUTTON_PIN = 16
STOP_BUTTON_PIN = 12
CONVEYOR_RELAY_PIN = 23
CONVEYOR_RELAY_PIN2 = 24
CONVEYOR_RELAY_PIN3 = 25

#open GPIO chip
chip = lgpio.gpiochip_open(0)

try:
    # Set up GPIO pins
    lgpio.gpio_claim_output(chip, CONVEYOR_RELAY_PIN, 0)
    lgpio.gpio_claim_input(chip, START_BUTTON_PIN, lgpio.SET_PULL_UP)

    def button_callback(handle, gpio, edge, tick):
        print("Button pressed")
        if edge == lgpio.FALLING_EDGE:
            lgpio.gpio_write(chip, CONVEYOR_RELAY_PIN, 1)  # Turn on the conveyor relay
        elif edge == lgpio.RISING_EDGE:
            lgpio.gpio_write(chip, CONVEYOR_RELAY_PIN, 0)

    cb = lgpio.callback(chip, START_BUTTON_PIN, lgpio.BOTH_EDGES, button_callback, debounce=50)

    print("Press CTRL-C to exit")
    while True:
        time.sleep(1)  # Keep program running

except KeyboardInterrupt:
    pass
finally:
    #cleanup
    cb.cancel()  # Remove callback
    lgpio.gpio_write(chip, CONVEYOR_RELAY_PIN, 0)  # Ensure relay is off
    lgpio.gpiochip_close(chip)  # Release GPIO resources
    print("\nCleaned up GPIO resources")