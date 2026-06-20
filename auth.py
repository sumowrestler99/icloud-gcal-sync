#!/usr/bin/env python3
"""
Run this once locally to authorize Google Calendar access.
It will open a browser, ask you to sign in, then save token.json to data/.
Copy data/token.json to your Synology alongside credentials.json.
"""

import os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar"]
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CREDENTIALS_FILE = os.path.join(DATA_DIR, "credentials.json")
TOKEN_FILE = os.path.join(DATA_DIR, "token.json")

os.makedirs(DATA_DIR, exist_ok=True)

if not os.path.exists(CREDENTIALS_FILE):
    print(f"ERROR: {CREDENTIALS_FILE} not found.")
    print("Download credentials.json from Google Cloud Console and place it in data/")
    exit(1)

flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
creds = flow.run_local_server(port=0)

with open(TOKEN_FILE, "w") as f:
    f.write(creds.to_json())

print(f"\nSuccess! Token saved to {TOKEN_FILE}")
print("Copy the data/ directory to your Synology before starting the container.")
