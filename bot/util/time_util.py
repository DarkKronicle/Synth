import re
from datetime import datetime, timedelta

from discord.ext import commands
from pytz import timezone


class IntervalConverter(commands.Converter):
    DAY_REGEX = re.compile(r'(\d{1,2}) day(s)?')
    WEEK_REGEX = re.compile(r'(\d{1,2}) week(s)?')
    MONTH_REGEX = re.compile(r'(\d{1,2}) month(s)?')

    async def convert(self, ctx, argument):
        low = argument.lower()
        match: re.Match = self.DAY_REGEX.search(low)
        if match:
            days = int(match.group(1))
            if days <= 0:
                raise commands.errors.BadArgument('Days has to be greater than 0!')
            return f'{days} days'
        match: re.Match = self.WEEK_REGEX.search(low)
        if match:
            weeks = int(match.group(1))
            if weeks <= 0:
                raise commands.errors.BadArgument('Weeks has to be great than 0!')
            return f'{weeks} weeks'
        match: re.Match = self.MONTH_REGEX.search(low)
        if match:
            months = int(match.group(1))
            if months >= 24 or months <= 0:
                raise commands.errors.BadArgument('Months has to be above zero and below 24!')
            return f'{months} months'
        return None


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


def _leading_zero(string):
    if len(string) > 1:
        return string
    return '0{0}'.format(string)


def human_digital(total_seconds):
    seconds = int(total_seconds % 60)
    minutes = int((total_seconds // 60) % 60)
    hours = int(total_seconds // 60 // 60 % 24)
    days = int(total_seconds // 60 // 60 // 24)
    builder = []
    if days > 0:
        builder.append(str(days))
    builder.append(_leading_zero(str(hours)))
    builder.append(_leading_zero(str(minutes)))
    builder.append(_leading_zero(str(seconds)))
    return ':'.join(builder)


def round_time(time_object=None, round_to=30 * 60):
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

    stripped_dt = time_object.replace(tzinfo=None, hour=0, minute=0, second=0)
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
