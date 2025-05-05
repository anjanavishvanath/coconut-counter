import lgpio
import time

# BCM pin numbers
START_BUTTON_PIN = 16
STOP_BUTTON_PIN = 12
CONVEYOR_RELAY_PIN = 23
CONVEYOR_RELAY_PIN2 = 24
CONVEYOR_RELAY_PIN3 = 25

#setup
chip = lgpio.gpiochip_open(0)

lgpio.gpio_claim_input(chip, START_BUTTON_PIN, pull=lgpio.PULL_UP)
lgpio.gpio_claim_input(chip, STOP_BUTTON_PIN, pull=lgpio.PULL_UP)

try:
    while True:
        startState = lgpio.gpio_read(chip, START_BUTTON_PIN)
        StopState = lgpio.gpio_read(chip, STOP_BUTTON_PIN)

        print("Start Button State: ", startState, "Stop Button State: ", StopState)
        time.sleep(10)
except KeyboardInterrupt:
    pass
finally:
    lgpio.gpio_release(chip, START_BUTTON_PIN)
    lgpio.gpio_release(chip, STOP_BUTTON_PIN)
    lgpio.gpiochip_close(chip)  