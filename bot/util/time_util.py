from datetime import datetime, timedelta

from dateutil.tz import gettz
from pytz import timezone


def human(total_seconds):
    seconds = total_seconds % 60
    minutes = (total_seconds // 60) % 60
    hours = total_seconds // 60 // 60 % 24
    days = total_seconds // 60 // 60 // 24
    builder = []
    if days > 0:
        builder.append(f"{int(days)} days")
    if hours > 0:
        builder.append(f"{int(hours)} hours")
    if minutes > 0:
        builder.append(f"{int(minutes)} minutes")
    if seconds > 0:
        builder.append(f"{int(seconds)} seconds")
    return ", ".join(builder)


def round_time(dt=None, round_to=30 * 60):
    """Round a datetime object to any time lapse in seconds
   dt : datetime.datetime object, default now.
   roundTo : Closest number of seconds to round to, default 1 minute.
   Author: Thierry Husson 2012 - Use it as you want but don't blame me.
   """
    if dt is None:
        zone = timezone('UTC')
        utc = timezone('UTC')
        dt = utc.localize(datetime.now())
        dt = dt.astimezone(zone)

    seconds = (dt.replace(tzinfo=None) - dt.replace(tzinfo=None, hour=0, minute=0, second=0)).seconds
    rounding = (seconds + round_to / 2) // round_to * round_to
    return dt + timedelta(0, rounding - seconds, -dt.microsecond)


def get_time_until_minute():
    return 60 - datetime.now().second


def floor_time(*, top=30):
    time = datetime.now(gettz('UTC'))
    num = time.minute
    while True:
        if num % top == 0:
            break
        num -= 1
    while num < 0:
        num += 60
        time = time.replace(hour=time.hour - 1)
    time = time.replace(minute=num, second=0, microsecond=0)
    return time


def ceil_time(*, top=30):
    time = datetime.now(gettz('UTC'))
    num = time.minute
    while True:
        if num % top == 0:
            break
        num += 1
    while num > 0:
        num -= 60
        time = time.replace(hour=time.hour + 1)
    time = time.replace(minute=num, second=0, microsecond=0)
    return time
