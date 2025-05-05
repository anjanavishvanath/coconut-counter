import lgpio
import time

# BCM pin numbers
START_BUTTON_PIN    = 16
STOP_BUTTON_PIN     = 12
CONVEYOR_RELAY_PIN  = 23

# Setup
chip = lgpio.gpiochip_open(0)

# Inputs with pull-ups
lgpio.gpio_claim_input(chip, START_BUTTON_PIN, lgpio.PULL_UP)
lgpio.gpio_claim_input(chip, STOP_BUTTON_PIN,  lgpio.PULL_UP)

# Relay output, start LOW (0 = off)
lgpio.gpio_claim_output(chip, CONVEYOR_RELAY_PIN, 0)

running = False

try:
    while True:
        start_state = lgpio.gpio_read(chip, START_BUTTON_PIN)
        stop_state  = lgpio.gpio_read(chip, STOP_BUTTON_PIN)

        # If not already running, a press of Start (HIGH->LOW) turns it on
        if not running and start_state == 0:
            lgpio.gpio_write(chip, CONVEYOR_RELAY_PIN, 1)
            running = True
            print("Conveyor STARTED")
            # wait for button release
            while lgpio.gpio_read(chip, START_BUTTON_PIN) == 0:
                time.sleep(0.01)

        # If running, a press of Stop turns it off
        if running and stop_state == 0:
            lgpio.gpio_write(chip, CONVEYOR_RELAY_PIN, 0)
            running = False
            print("Conveyor STOPPED")
            # wait for button release
            while lgpio.gpio_read(chip, STOP_BUTTON_PIN) == 0:
                time.sleep(0.01)

        time.sleep(0.05)

except KeyboardInterrupt:
    pass

finally:
    # cleanup
    lgpio.gpiochip_close(chip)
