# icloud-gcal-sync

One-way sync from iCloud Calendar to Google Calendar, packaged as a Docker container. Designed to run on a Synology NAS.

## How it works

The container connects to iCloud via CalDAV and Google Calendar via the Google Calendar API, then periodically mirrors your iCloud events to Google Calendar. Events deleted from iCloud are also removed from Google Calendar.

## Prerequisites

- Apple ID with an app-specific password
- Google Cloud project with the Calendar API enabled and OAuth 2.0 credentials
- Docker (tested on Synology DSM)
- Python 3 installed locally (for one-time Google authorization)

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/sumowrestler99/icloud-gcal-sync.git
cd icloud-gcal-sync
```

### 2. iCloud app-specific password

1. Go to [appleid.apple.com](https://appleid.apple.com) and sign in
2. Under **Sign-In and Security**, choose **App-Specific Passwords**
3. Generate a new password and label it `calendar-sync`
4. Save it — you'll need it for the `.env` file

### 3. Google Calendar credentials

1. Go to [console.cloud.google.com](https://console.cloud.google.com) and create a project
2. Enable the **Google Calendar API**
3. Go to **APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID**
4. Choose **Desktop app**, then download the JSON file
5. Place it in the `data/` directory and rename it `credentials.json`

```bash
mkdir data
mv ~/Downloads/credentials.json data/
```

### 4. Authorize Google (run once locally)

Install dependencies and run the auth script. This opens a browser to authorize access to your Google Calendar and saves a token to `data/token.json`.

```bash
pip3 install -r requirements.txt
python3 auth.py
```

### 5. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
ICLOUD_USERNAME=you@icloud.com
ICLOUD_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
ICLOUD_CALENDAR_NAME=
```

### 6. Deploy to Synology

```bash
./deploy.sh <user> <synology-host>
```

Then SSH in and start the container:

```bash
ssh user@synology
cd /volume1/docker/icloud-gcal-sync
docker compose up -d
```

---

## Configuration

Credentials go in `.env`. Non-sensitive settings can also be overridden in the `environment:` section of `docker-compose.yml`.

| Variable | Default | Description |
|---|---|---|
| `ICLOUD_USERNAME` | required | Apple ID email |
| `ICLOUD_APP_PASSWORD` | required | App-specific password |
| `ICLOUD_CALENDAR_NAME` | _(all)_ | Specific calendar name, or blank to sync all |
| `GOOGLE_CALENDAR_ID` | `primary` | Target Google Calendar |
| `SYNC_PAST_DAYS` | `30` | How many days back to sync |
| `SYNC_FUTURE_DAYS` | `365` | How many days forward to sync |
| `SYNC_INTERVAL_MINUTES` | `15` | How often to sync |

---

## Notes

- `data/` is mounted as a Docker volume so the Google token persists across container restarts and is refreshed automatically
- Events synced to Google Calendar are tagged with the iCloud UID in extended properties, which is how the sync tracks them across runs
- Logs are capped at 15MB (3 × 5MB files) via Docker's json-file logging driver
