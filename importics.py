import sqlite3
import time
from pathlib import Path
from datetime import datetime, timedelta
from dateutil.rrule import rrulestr
from dateutil.tz import gettz
from icalendar import Calendar

DB_PATH = str(Path.home() / ".calendar" / "calendardb")
DEFAULT_TZ = gettz("Europe/Vienna")

def expand_recurring_events(calendar):
    expanded = []
    for component in calendar.walk():
        if component.name != "VEVENT":
            continue

        summary = str(component.get("SUMMARY", ""))
        print(f"🌀 Recurring: {summary}")

        dtstart = component.get("DTSTART").dt
        dtend = component.get("DTEND").dt

        if isinstance(dtstart, datetime) and dtstart.tzinfo is None:
            dtstart = dtstart.replace(tzinfo=DEFAULT_TZ)
        elif not isinstance(dtstart, datetime):
            dtstart = datetime.combine(dtstart, datetime.min.time(), tzinfo=DEFAULT_TZ)

        if isinstance(dtend, datetime) and dtend.tzinfo is None:
            dtend = dtend.replace(tzinfo=DEFAULT_TZ)
        elif not isinstance(dtend, datetime):
            dtend = datetime.combine(dtend, datetime.min.time(), tzinfo=DEFAULT_TZ)

        rrule_field = component.get("RRULE")
        if not rrule_field:
            expanded.append((summary, dtstart, dtend, str(component.get("UID"))))
            continue

        try:
            rrule_str_val = "\n".join(
                f"{key}={','.join(map(str, val))}" for key, val in rrule_field.items()
                if isinstance(val, list)
            )
            rule = rrulestr(rrule_str_val, dtstart=dtstart)
            exdates = []
            for ex in component.get("EXDATE", []):
                if hasattr(ex, "dts"):
                    exdates.extend([dt.dt.replace(tzinfo=DEFAULT_TZ) for dt in ex.dts])
            for occurrence_start in rule:
                if occurrence_start in exdates:
                    continue
                delta = dtend - dtstart
                occurrence_end = occurrence_start + delta
                expanded.append((summary, occurrence_start, occurrence_end, str(component.get("UID")) + f"-{int(occurrence_start.timestamp())}"))
        except Exception as e:
            print(f"⚠️  Failed to expand recurrence: {e}")
            continue
    return expanded

def insert_into_qalendar(instances):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute("SELECT CalendarId FROM Calendars LIMIT 1")
    cal_id = cur.fetchone()[0]

    inserted = 0
    for summary, start, end, uid in instances:
        start_ts = int(start.timestamp())
        end_ts = int(end.timestamp())
        now = int(time.time())

        # DELETE old instance with same UID before re-inserting (overwrite mode)
        cur.execute("DELETE FROM Components WHERE Uid = ?", (uid,))

        cur.execute("""
            INSERT INTO Components (
                CalendarId, ComponentType, Flags, DateStart, DateEnd,
                Summary, Location, Description, Status, Uid, Until,
                AllDay, CreatedTime, ModifiedTime, Tzid, TzOffset
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cal_id, 1, -1, start_ts, end_ts,
            summary, "", "", -1, uid, -1,
            0, now, now, ":Europe/Vienna", 7200
        ))
        inserted += 1

    con.commit()
    con.close()
    print(f"✅ Inserted {inserted} new event(s) into Qalendar.")

if __name__ == "__main__":
    import sys
    with open(sys.argv[1], "rb") as f:
        cal = Calendar.from_ical(f.read())
    instances = expand_recurring_events(cal)
    insert_into_qalendar(instances)
