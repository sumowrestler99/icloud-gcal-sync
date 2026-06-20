import os

ICLOUD_USERNAME = os.environ["ICLOUD_USERNAME"]
ICLOUD_APP_PASSWORD = os.environ["ICLOUD_APP_PASSWORD"]
ICLOUD_CALENDAR_NAME = os.environ.get("ICLOUD_CALENDAR_NAME", "")  # blank = all calendars

GOOGLE_CALENDAR_ID = os.environ.get("GOOGLE_CALENDAR_ID", "primary")

SYNC_PAST_DAYS = int(os.environ.get("SYNC_PAST_DAYS", "30"))
SYNC_FUTURE_DAYS = int(os.environ.get("SYNC_FUTURE_DAYS", "365"))
SYNC_INTERVAL_MINUTES = int(os.environ.get("SYNC_INTERVAL_MINUTES", "15"))

DATA_DIR = os.environ.get("DATA_DIR", "/app/data")
