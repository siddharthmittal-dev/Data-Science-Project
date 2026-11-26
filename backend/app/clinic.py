"""Owner-confirmed operating hours. All published times use the clinic timezone."""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.config import get_settings

HOURS = "Monday–Friday 08:00–18:00; Saturday 09:00–13:00; Sunday closed"


def bounds(day):
    return (8, 18) if day.weekday() < 5 else (9, 13) if day.weekday() == 5 else None


def slots_for_day(day, doctor_id):
    from app.models import Slot
    hours = bounds(day)
    if hours is None:
        return []
    start, end = hours
    zone = ZoneInfo(get_settings().clinic_timezone)
    first = datetime.combine(day, time(start), tzinfo=zone)
    return [Slot(doctor_id=doctor_id, starts_at=first + timedelta(minutes=30 * i),
                 ends_at=first + timedelta(minutes=30 * (i + 1))) for i in range((end - start) * 2)]


def format_when(dt):
    local = dt.astimezone(ZoneInfo(get_settings().clinic_timezone))
    return f"{local:%a} {local.day} {local:%b}, {local:%H:%M}"


def valid_slot(slot):
    local = slot.starts_at.astimezone(ZoneInfo(get_settings().clinic_timezone))
    hours = bounds(local.date())
    return bool(hours and local.minute in (0, 30) and local.second == 0 and local.microsecond == 0
                and hours[0] <= local.hour < hours[1]
                and slot.ends_at - slot.starts_at == timedelta(minutes=30))
