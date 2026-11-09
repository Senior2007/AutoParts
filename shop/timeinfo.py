import calendar
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone


def project_timezone():
    return ZoneInfo(settings.TIME_ZONE)


def format_utc_offset(tz_info):
    offset = timezone.now().astimezone(tz_info).utcoffset()
    if offset is None:
        return ''
    total_minutes = int(offset.total_seconds() // 60)
    hours, minutes = divmod(abs(total_minutes), 60)
    sign = '+' if total_minutes >= 0 else '-'
    return f'UTC{sign}{hours:02d}:{minutes:02d}'


def calendar_text():
    today = timezone.now().astimezone(project_timezone()).date()
    return calendar.month(today.year, today.month)


def base_time_context():
    tz_info = project_timezone()
    now_utc = timezone.now()
    now_local = now_utc.astimezone(tz_info)
    return {
        'now_utc': now_utc,
        'now_local': now_local,
        'server_timezone': tz_info.key,
        'timezone_offset': format_utc_offset(tz_info),
        'text_calendar': calendar_text(),
    }
