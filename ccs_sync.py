import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from google.oauth2 import service_account
from googleapiclient.discovery import build

CCS_URL = "https://ccsplus.ual.com/calendarsyncapi/api/Calendar/GetCalendar"

CALENDAR_ID = "YOUR_CALENDAR_ID"

CHICAGO = ZoneInfo("America/Chicago")

def fetch_ccs():
    r = requests.get(CCS_URL)
    r.raise_for_status()
    return r.json()["Response"]["CrewSchedule"]

def to_dt(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))

def get_service():
    creds = service_account.Credentials.from_service_account_file(
        "service_account.json",
        scopes=["https://www.googleapis.com/auth/calendar"]
    )
    return build("calendar", "v3", credentials=creds)

def delete_existing(service):
    page_token = None
    while True:
        events = service.events().list(
            calendarId=CALENDAR_ID,
            privateExtendedProperty="source=CCS_SYNC",
            pageToken=page_token
        ).execute()

        for e in events.get("items", []):
            service.events().delete(calendarId=CALENDAR_ID, eventId=e["id"]).execute()

        page_token = events.get("nextPageToken")
        if not page_token:
            break

def build_events(schedule):
    events = []

    # Day Offs
    for d in schedule.get("DayOffs", []):
        start = to_dt(d["DayOff"]).astimezone(CHICAGO)
        end = start.replace(hour=23, minute=59)

        events.append(("Day Off", start, end))

    # Reserves / Assignments
    for a in schedule.get("NonFlyingAssignments", []):
        start = to_dt(a["UTCStartDate"]).astimezone(CHICAGO)
        end = to_dt(a["UTCEndDate"]).astimezone(CHICAGO)

        events.append(("RSA Reserve", start, end))

    # Flights (future-proof)
    for p in schedule.get("Pairings", []):
        start = to_dt(p["UTCStartDate"]).astimezone(CHICAGO)
        end = to_dt(p["UTCEndDate"]).astimezone(CHICAGO)

        events.append(("Trip", start, end))

    return events

def insert(service, events):
    for title, start, end in events:
        service.events().insert(
            calendarId=CALENDAR_ID,
            body={
                "summary": title,
                "start": {"dateTime": start.isoformat()},
                "end": {"dateTime": end.isoformat()},
                "extendedProperties": {
                    "private": {"source": "CCS_SYNC"}
                }
            }
        ).execute()

def main():
    schedule = fetch_ccs()
    service = get_service()

    delete_existing(service)
    events = build_events(schedule)
    insert(service, events)

if __name__ == "__main__":
    main()
