import os

ICLOUD_USERNAME = os.environ["ICLOUD_USERNAME"]
ICLOUD_APP_PASSWORD = os.environ["ICLOUD_APP_PASSWORD"]

# Comma-separated "iCloud name=Google calendar" pairs, e.g. "Home=primary,Work".
# Blank = every iCloud calendar syncs to a Google calendar of the same name.
CALENDAR_MAP = os.environ.get("CALENDAR_MAP", "")

SYNC_PAST_DAYS = int(os.environ.get("SYNC_PAST_DAYS", "30"))
SYNC_FUTURE_DAYS = int(os.environ.get("SYNC_FUTURE_DAYS", "365"))
SYNC_INTERVAL_MINUTES = int(os.environ.get("SYNC_INTERVAL_MINUTES", "15"))

DATA_DIR = os.environ.get("DATA_DIR", "/app/data")
