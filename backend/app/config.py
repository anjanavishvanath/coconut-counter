from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# ─── GPIO setup ─────────────────────────────────────────────────────
# BCM pin numbers
START_BUTTON_PIN = 22 #16
STOP_BUTTON_PIN  = 16 #12
CONVEYOR_RELAY_PIN = 17 #was 25 turned to Relay 4
BUZZEER_PIN = 23 # Relay 3

# ─── SMTP configuration ─────────────────────────────────────────────
# Data is pulled from a .env file in the same directory as this script.
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_FROM    = os.getenv("EMAIL_FROM")
EMAIL_TO      = os.getenv("EMAIL_TO")