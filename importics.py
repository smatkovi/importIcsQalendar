import sys
import sqlite3
import time
from datetime import datetime, timedelta, date, time as dtime
from zoneinfo import ZoneInfo
from pathlib import Path


from icalendar import Calendar, Event
from dateutil.rrule import rrulestr
from dateutil.tz import gettz

DB_PATH = str(Path.home() / ".calendar" / "calendardb")
TIMEZONE = ZoneInfo("Europe/Vienna")

def parse_ics(path):
    with open(path, "rb") as f:
        return Calendar.from_ical(f.read())

def expand_recurring_events(cal):
    instances = []

    for component in cal.walk():
        if component.name != "VEVENT":
            continue

        uid = str(component.get("UID"))
        summary = str(component.get("SUMMARY", ""))
        location = str(component.get("LOCATION", ""))
        description = str(component.get("DESCRIPTION", ""))
        tzinfo = TIMEZONE

        dtstart = component.get("DTSTART").dt
        dtend = component.get("DTEND").dt if component.get("DTEND") else dtstart

        if isinstance(dtstart, date) and not isinstance(dtstart, datetime):
            dtstart = datetime.combine(dtstart, dtime.min)
        if isinstance(dtend, date) and not isinstance(dtend, datetime):
            dtend = datetime.combine(dtend, dtime.min)

        dtstart = dtstart.replace(tzinfo=tzinfo)
        dtend = dtend.replace(tzinfo=tzinfo)

        rrule_raw = component.get("RRULE")
        if rrule_raw:
            try:
                print(f"🌀 Recurring: {summary}")
                rule = rrulestr(str(rrule_raw.to_ical().decode()), dtstart=dtstart)
                exdates = component.get("EXDATE")
                exclusions = set()
                if exdates:
                    if not isinstance(exdates, list):
                        exdates = [exdates]
                    for ex in exdates:
                        for exval in ex.dts:
                            exclusions.add(exval.dt.replace(tzinfo=tzinfo))

                for recur_dt in rule:
                    if recur_dt in exclusions:
                        continue
                    duration = dtend - dtstart
                    instances.append({
                        "uid": f"{uid}-{int(recur_dt.timestamp())}",
                        "summary": summary,
                        "location": location,
                        "description": description,
                        "start": recur_dt,
                        "end": recur_dt + duration,
                    })
            except Exception as e:
                print(f"⚠️  Failed to expand recurrence: {e}")
        else:
            instances.append({
                "uid": uid,
                "summary": summary,
                "location": location,
                "description": description,
                "start": dtstart,
                "end": dtend,
            })
    return instances

def insert_into_qalendar(events):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute("SELECT CalendarId FROM Calendars LIMIT 1")
    calendar_id = cur.fetchone()[0]

    inserted = 0
    for ev in events:
        uid = ev["uid"]
        summary = ev["summary"]
        location = ev["location"]
        description = ev["description"]
        start = int(ev["start"].timestamp())
        end = int(ev["end"].timestamp())

        cur.execute("DELETE FROM Components WHERE Uid = ?", (uid,))
        cur.execute("""
            INSERT INTO Components (
                CalendarId, ComponentType, Flags,
                DateStart, DateEnd, Summary,
                Location, Description, Status,
                Uid, Until, AllDay,
                CreatedTime, ModifiedTime, Tzid, TzOffset
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            calendar_id, 1, -1, start, end,
            summary, location, description, 0,
            uid, -1, 0,
            int(time.time()), int(time.time()),
            ":Europe/Vienna", 7200
        ))
        inserted += 1

    con.commit()
    con.close()
    print(f"✅ Inserted {inserted} new event(s) into Qalendar.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 importics.py path/to/file.ics")
        sys.exit(1)

    ics_path = sys.argv[1]
    cal = parse_ics(ics_path)
    events = expand_recurring_events(cal)
    insert_into_qalendar(events)
