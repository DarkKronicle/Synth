from datetime import datetime, timedelta

from pytz import timezone


def human(total_seconds):
    seconds = int(total_seconds % 60)
    minutes = int((total_seconds // 60) % 60)
    hours = int(total_seconds // 60 // 60 % 24)
    days = int(total_seconds // 60 // 60 // 24)
    builder = []
    if days > 0:
        builder.append('{0} days'.format(str(days)))
    if hours > 0:
        builder.append('{0} hours'.format(int(hours)))
    if minutes > 0:
        builder.append('{0} minutes'.format(int(minutes)))
    if seconds > 0:
        builder.append('{0} seconds'.format(str(seconds)))
    return ', '.join(builder)


def round_time(time_object=None, round_to=1800):
    """
    Round a datetime object to any time lapse in seconds
    dt : datetime.datetime object, default now.
    roundTo : Closest number of seconds to round to, default 1 minute.
    Author: Thierry Husson 2012 - Use it as you want but don't blame me.
    """
    if time_object is None:
        zone = timezone('UTC')
        utc = timezone('UTC')
        time_object = utc.localize(datetime.now())
        time_object = time_object.astimezone(zone)

    stripped_dt = time_object.replace(tzinfo=None) - time_object.replace(tzinfo=None)
    seconds = (time_object.replace(tzinfo=None) - stripped_dt).seconds
    rounding = (seconds + round_to / 2) // round_to * round_to
    return time_object + timedelta(0, rounding - seconds, -time_object.microsecond)


def get_utc():
    return datetime.utcnow()


def get_time_until_minute():
    return 60 - datetime.now().second


def floor_time(*, top=30, time_like=None):
    if time_like is None:
        time_like = get_utc()
    num = time_like.minute
    while True:
        if num % top == 0:
            break
        num -= 1
    while num < 0:
        num += 60
        time_like = time_like.replace(hour=time_like.hour - 1)
    return time_like.replace(minute=num, second=0, microsecond=0)


def ceil_time(*, top=30, time_like=None):
    if time_like is None:
        time_like = get_utc()
    num = time_like.minute
    while num % top != 0:
        num += 1
    while num > 60:
        num -= 60
        time_like = time_like.replace(hour=time_like.hour + 1)
    return time_like.replace(minute=num, second=0, microsecond=0)
