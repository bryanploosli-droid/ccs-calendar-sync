mport os
import json
import logging
import requests
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ----------------------------
# CONFIG
# ----------------------------
CCS_URL = "https://ccsplus.ual.com/calendarsyncapi/api/Calendar/GetCalendar"

GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("ccs-sync")


# ----------------------------
# SAFE SESSION (RETRIES)
# ----------------------------
def build_session():
    session = requests.Session()

    retries = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )

    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session


# ----------------------------
# FETCH CCS DATA
# ----------------------------
def fetch_ccs_schedule(session):
    logger.info("Fetching CCS schedule...")

    try:
        response = session.get(CCS_URL, timeout=20)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"CCS request failed: {e}")
        return None

    try:
        data = response.json()
    except Exception:
        logger.error("Failed to parse JSON from CCS response")
        return None

    return data


# ----------------------------
# NORMALIZE DATA (SAFE)
# ----------------------------
def normalize_schedule(raw_data):
    """
    Defensive normalization so API changes don't break pipeline.
    """
    if not raw_data:
        return []

    events = []

    # Try common structures safely
    possible_keys = ["events", "data", "schedule", "result"]

    source = None
    for key in possible_keys:
        if isinstance(raw_data, dict) and key in raw_data:
            source = raw_data[key]
            break

    if source is None:
        # assume raw list
        source = raw_data if isinstance(raw_data, list) else []

    for item in source:
        try:
            event = {
                "title": str(item.get("title", "CCS Event")),
                "start": item.get("start"),
                "end": item.get("end"),
                "location": str(item.get("location", "")),
                "id": str(item.get("id", "")),
            }

            # skip broken entries
            if not event["start"]:
                continue

            events.append(event)

        except Exception:
            continue

    logger.info(f"Normalized {len(events)} events")
    return events


# ----------------------------
# GOOGLE CALENDAR (PLACEHOLDER HOOK)
# ----------------------------
def sync_to_google_calendar(events):
    """
    Replace this with your actual Google Calendar API logic.
    Kept isolated so CCS logic stays stable.
    """
    logger.info("Syncing to Google Calendar...")

    for e in events:
        logger.info(f"Would sync: {e['title']} @ {e['start']}")

    # TODO: implement real insertion logic
    return True


# ----------------------------
# MAIN
# ----------------------------
def main():
    logger.info("=== CCS SYNC START ===")

    session = build_session()

    raw = fetch_ccs_schedule(session)
    if raw is None:
        logger.error("No data received from CCS. Exiting safely.")
        return

    events = normalize_schedule(raw)

    if not events:
        logger.warning("No events to sync")
        return

    success = sync_to_google_calendar(events)

    if success:
        logger.info("Sync completed successfully")
    else:
        logger.error("Sync failed during Google Calendar step")

    logger.info("=== CCS SYNC END ===")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # IMPORTANT: prevents GitHub Actions from showing ugly stack traces
        logger.error(f"Fatal error: {e}")
        exit(1)
