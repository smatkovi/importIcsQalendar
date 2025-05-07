import os
import sys
import sqlite3
import datetime
from icalendar import Calendar

DB_PATH = os.path.expanduser("~/.calendar/calendardb")

TYPE_MAP = {
    "VEVENT": 1,
    "VTODO": 2,
    "VJOURNAL": 3,
}

def parse_ics(file_path):
    with open(file_path, "rb") as f:
        cal = Calendar.from_ical(f.read())

    events = []
    for component in cal.walk():
        if component.name not in TYPE_MAP:
            continue

        uid = str(component.get("UID", ""))
        summary = str(component.get("SUMMARY", ""))
        location = str(component.get("LOCATION", ""))
        description = str(component.get("DESCRIPTION", ""))
        dtstart = component.get("DTSTART")
        dtend = component.get("DTEND") or dtstart

        # Convert datetime.date to datetime.datetime if needed
        if hasattr(dtstart.dt, "timestamp"):
            start_ts = int(dtstart.dt.timestamp())
        else:
            start_ts = int(datetime.datetime.combine(dtstart.dt, datetime.time()).timestamp())

        if hasattr(dtend.dt, "timestamp"):
            end_ts = int(dtend.dt.timestamp())
        else:
            end_ts = int(datetime.datetime.combine(dtend.dt, datetime.time()).timestamp())

        events.append({
            "type": TYPE_MAP[component.name],
            "summary": summary,
            "location": location,
            "description": description,
            "uid": uid,
            "start": start_ts,
            "end": end_ts,
        })

    return events

def insert_events(events):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Use CalendarId = 1 (DEFAULT_SYNC)
    calendar_id = 1

    count = 0
    for e in events:
        cur.execute("""
            INSERT INTO Components (
                CalendarId, ComponentType, Flags, DateStart, DateEnd,
                Summary, Location, Description, Status, Uid,
                Until, AllDay, CreatedTime, ModifiedTime, Tzid, TzOffset
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            calendar_id, e["type"], -1, e["start"], e["end"],
            e["summary"], e["location"], e["description"], -1, e["uid"],
            -1, 0, int(datetime.datetime.now().timestamp()), int(datetime.datetime.now().timestamp()),
            ":Europe/Vienna", 7200
        ))
        new_id = cur.lastrowid
        cur.execute("INSERT INTO Instances (Id, DateStart, DateEnd) VALUES (?, ?, ?)",
                    (new_id, e["start"], e["end"]))
        count += 1

    conn.commit()
    conn.close()
    print(f"Imported {count} events successfully.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 importics.py <file.ics>")
        sys.exit(1)

    events = parse_ics(sys.argv[1])
    insert_events(events)
