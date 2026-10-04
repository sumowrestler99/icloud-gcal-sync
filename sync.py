#!/usr/bin/env python3
"""iCloud → Google Calendar one-way sync."""

import hashlib
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import caldav
from dateutil import parser as dateparser
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]
TOKEN_FILE = os.path.join(config.DATA_DIR, "token.json")
CREDENTIALS_FILE = os.path.join(config.DATA_DIR, "credentials.json")


# ── Google auth ───────────────────────────────────────────────────────────────

def get_google_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_FILE, "w") as f:
                f.write(creds.to_json())
        else:
            log.error(
                "No valid token found. Run auth.py locally to generate %s, "
                "then place it in the data/ directory.", TOKEN_FILE
            )
            sys.exit(1)
    return build("calendar", "v3", credentials=creds)


# ── iCloud CalDAV ─────────────────────────────────────────────────────────────

def get_icloud_calendars():
    """Return {display name: calendar} for iCloud calendars that hold events (skips reminder lists)."""
    client = caldav.DAVClient(
        url="https://caldav.icloud.com",
        username=config.ICLOUD_USERNAME,
        password=config.ICLOUD_APP_PASSWORD,
    )
    return {
        c.get_display_name(): c
        for c in client.principal().calendars()
        if "VEVENT" in c.get_supported_components()
    }


def get_icloud_events(calendars):
    start = datetime.now(timezone.utc) - timedelta(days=config.SYNC_PAST_DAYS)
    end = datetime.now(timezone.utc) + timedelta(days=config.SYNC_FUTURE_DAYS)

    events = []
    for cal in calendars:
        for event in cal.search(start=start, end=end, event=True, expand=True):
            vevent = event.icalendar_component
            events.append(parse_ical_event(vevent, event.url))
    return events


def parse_ical_event(vevent, url):
    uid = str(vevent.get("UID", ""))
    summary = str(vevent.get("SUMMARY", "(No title)"))
    description = str(vevent.get("DESCRIPTION", "") or "")
    location = str(vevent.get("LOCATION", "") or "")

    dtstart = vevent.get("DTSTART").dt
    dtend = vevent.get("DTEND").dt if vevent.get("DTEND") else None

    if isinstance(dtstart, datetime):
        if dtstart.tzinfo is None:
            dtstart = dtstart.replace(tzinfo=timezone.utc)
        all_day = False
    else:
        all_day = True

    if dtend and isinstance(dtend, datetime) and dtend.tzinfo is None:
        dtend = dtend.replace(tzinfo=timezone.utc)

    # Expanded recurring occurrences share a UID; RECURRENCE-ID tells them apart.
    key = uid
    if uid and vevent.get("RECURRENCE-ID"):
        key = f"{uid}|{vevent.get('RECURRENCE-ID').dt.isoformat()}"

    return {
        "uid": uid,
        "key": key,
        "summary": summary,
        "description": description,
        "location": location,
        "dtstart": dtstart,
        "dtend": dtend,
        "all_day": all_day,
        "url": str(url),
    }


# ── Google Calendar helpers ───────────────────────────────────────────────────

def add_existing(result, key, event_id, hash_):
    """Record a synced event; extra events with the same key are kept as duplicates to delete."""
    if key in result:
        result[key]["duplicates"].append(event_id)
    else:
        result[key] = {"id": event_id, "hash": hash_, "duplicates": []}


def content_hash(ev):
    key = f"{ev['summary']}|{ev['description']}|{ev['location']}|{ev['dtstart']}|{ev['dtend']}|{ev['all_day']}"
    return hashlib.md5(key.encode()).hexdigest()


def to_google_event(ev):
    body = {
        "summary": ev["summary"],
        "description": ev["description"] or None,
        "location": ev["location"] or None,
        "extendedProperties": {
            "private": {"icloudUID": ev["key"], "source": "icloud", "contentHash": content_hash(ev)}
        },
    }

    if ev["all_day"]:
        body["start"] = {"date": ev["dtstart"].strftime("%Y-%m-%d")}
        end_date = ev["dtend"] if ev["dtend"] else ev["dtstart"] + timedelta(days=1)
        body["end"] = {"date": end_date.strftime("%Y-%m-%d")}
    else:
        body["start"] = {"dateTime": ev["dtstart"].isoformat()}
        end = ev["dtend"] if ev["dtend"] else ev["dtstart"] + timedelta(hours=1)
        body["end"] = {"dateTime": end.isoformat()}

    return body


def get_existing_google_events(service, calendar_id):
    result = {}
    page_token = None
    while True:
        resp = service.events().list(
            calendarId=calendar_id,
            privateExtendedProperty="source=icloud",
            pageToken=page_token,
            maxResults=500,
        ).execute()
        for item in resp.get("items", []):
            private = item.get("extendedProperties", {}).get("private", {})
            uid = private.get("icloudUID")
            if uid:
                add_existing(result, uid, item["id"], private.get("contentHash"))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return result


def get_google_calendars(service):
    calendars = []
    page_token = None
    while True:
        resp = service.calendarList().list(pageToken=page_token).execute()
        calendars.extend(resp.get("items", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return calendars


def find_google_calendar(google_calendars, target):
    """Return the calendar ID for target, a calendar ID or name, or None if no such calendar exists."""
    for cal in google_calendars:
        if (target == "primary" and cal.get("primary")) or target in (cal["id"], cal.get("summary")):
            return cal["id"]
    if target == "primary" or "@" in target:
        return target
    return None


def create_google_calendar(service, google_calendars, target):
    log.info("Creating Google calendar '%s'", target)
    created = service.calendars().insert(body={"summary": target}).execute()
    google_calendars.append(created)
    return created["id"]


def remove_untargeted_events(service, google_calendars, target_ids):
    """Delete synced events from owned calendars that are no longer sync targets (e.g. after remapping)."""
    for cal in google_calendars:
        if cal["id"] in target_ids or cal.get("accessRole") != "owner":
            continue
        existing = get_existing_google_events(service, cal["id"])
        event_ids = [eid for meta in existing.values() for eid in [meta["id"], *meta["duplicates"]]]
        if not event_ids:
            continue
        log.info("[%s] No longer a sync target, removing %d synced events", cal["id"], len(event_ids))
        for event_id in event_ids:
            try:
                service.events().delete(calendarId=cal["id"], eventId=event_id).execute()
            except HttpError as e:
                log.warning("Failed to delete event %s: %s", event_id, e)


# ── Sync ──────────────────────────────────────────────────────────────────────

def get_calendar_targets(icloud_names):
    """Return {google target: [iCloud calendar names]}."""
    if not config.CALENDAR_MAP:
        return {name: [name] for name in icloud_names}

    # Group by target so iCloud calendars sharing a Google calendar sync in one pass;
    # syncing them separately would delete each other's events.
    targets = {}
    for entry in config.CALENDAR_MAP.split(","):
        if not entry.strip():
            continue
        icloud_name, _, google_target = entry.partition("=")
        icloud_name = icloud_name.strip()
        google_target = google_target.strip() or icloud_name
        targets.setdefault(google_target, []).append(icloud_name)
    return targets


def sync():
    log.info("Starting iCloud → Google Calendar sync")

    service = get_google_service()
    icloud_calendars = get_icloud_calendars()
    targets = get_calendar_targets(icloud_calendars)

    missing = [n for names in targets.values() for n in names if n not in icloud_calendars]
    if missing:
        # Bail out rather than sync an empty set, which would delete everything in Google.
        log.error("Calendar(s) not found in iCloud: %s", ", ".join(missing))
        sys.exit(1)

    google_calendars = get_google_calendars(service)
    target_ids = set()
    for target, icloud_names in targets.items():
        icloud_events = get_icloud_events([icloud_calendars[n] for n in icloud_names])
        calendar_id = find_google_calendar(google_calendars, target)
        if not calendar_id:
            if not icloud_events:
                continue  # don't create Google calendars for empty iCloud calendars
            calendar_id = create_google_calendar(service, google_calendars, target)
        target_ids.add(calendar_id)
        sync_calendar(service, calendar_id, icloud_events)

    remove_untargeted_events(service, google_calendars, target_ids)


def sync_calendar(service, calendar_id, icloud_events):
    existing = get_existing_google_events(service, calendar_id)

    log.info("[%s] Found %d iCloud events, %d already synced to Google",
             calendar_id, len(icloud_events), len(existing))

    created = updated = skipped = deleted = 0
    seen_uids = set()

    for ev in icloud_events:
        uid = ev["key"]
        if not uid:
            skipped += 1
            continue
        seen_uids.add(uid)
        body = to_google_event(ev)

        try:
            if uid in existing:
                if existing[uid]["hash"] == content_hash(ev):
                    skipped += 1
                    continue
                service.events().update(
                    calendarId=calendar_id,
                    eventId=existing[uid]["id"],
                    body=body,
                ).execute()
                updated += 1
            else:
                service.events().insert(
                    calendarId=calendar_id,
                    body=body,
                ).execute()
                created += 1
        except HttpError as e:
            log.warning("Failed to sync event '%s': %s", ev["summary"], e)

    for uid, meta in existing.items():
        stale = meta["duplicates"] + ([meta["id"]] if uid not in seen_uids else [])
        for event_id in stale:
            try:
                service.events().delete(
                    calendarId=calendar_id,
                    eventId=event_id,
                ).execute()
                deleted += 1
            except HttpError as e:
                log.warning("Failed to delete event %s: %s", uid, e)

    log.info("[%s] Done. Created: %d, Updated: %d, Deleted: %d, Skipped: %d",
             calendar_id, created, updated, deleted, skipped)


if __name__ == "__main__":
    os.makedirs(config.DATA_DIR, exist_ok=True)
    interval = config.SYNC_INTERVAL_MINUTES * 60
    log.info("Sync interval: %d minutes", config.SYNC_INTERVAL_MINUTES)

    while True:
        try:
            sync()
        except Exception as e:
            log.error("Sync failed: %s", e, exc_info=True)
        log.info("Next sync in %d minutes", config.SYNC_INTERVAL_MINUTES)
        time.sleep(interval)
