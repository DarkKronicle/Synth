"""
Released under MPL v2

Copyright Rapptz, DarkKronicle

Original: https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/utils/time.py
"""


import datetime
import parsedatetime as pdt
from dateutil.relativedelta import relativedelta
from bot.util.formats import Plural, human_join
from discord.ext import commands
import re
from bot.util import time_util as tutil


class ShortTime:
    compiled = re.compile("""(?:(?P<years>[0-9])(?:years?|y))?             # e.g. 2y
                             (?:(?P<months>[0-9]{1,2})(?:months?|mo))?     # e.g. 2months
                             (?:(?P<weeks>[0-9]{1,4})(?:weeks?|w))?        # e.g. 10w
                             (?:(?P<days>[0-9]{1,5})(?:days?|d))?          # e.g. 14d
                             (?:(?P<hours>[0-9]{1,5})(?:hours?|h))?        # e.g. 12h
                             (?:(?P<minutes>[0-9]{1,5})(?:minutes?|m))?    # e.g. 10m
                             (?:(?P<seconds>[0-9]{1,5})(?:seconds?|s))?    # e.g. 15s
                          """, re.VERBOSE)

    def __init__(self, argument, *, now=None):
        match = self.compiled.fullmatch(argument)
        if match is None or not match.group(0):
            raise commands.BadArgument('invalid time provided')

        data = {k: int(v) for k, v in match.groupdict(default=0).items()}
        if now is None:
            now = tutil.get_utc()
        self.dt = now + relativedelta(**data)

    @classmethod
    async def convert(cls, ctx, argument):
        return cls(argument, now=ctx.message.created_at)


class HumanTime:
    ptc = pdt.Constants()
    ptc.YearParseStyle = 0
    ptc.DOWParseStyle = -1

    past_calendar = pdt.Calendar(constants=ptc, version=pdt.VERSION_CONTEXT_STYLE)

    future_calendar = pdt.Calendar(version=pdt.VERSION_CONTEXT_STYLE)

    def __init__(self, argument, *, now=None):
        if now is None:
            now = tutil.get_utc()
        now = now or datetime.datetime.utcnow()
        dt, status = self.future_calendar.parseDT(argument, sourceTime=now)
        if not status.hasDateOrTime:
            raise commands.BadArgument('Invalid time provided, try `tomorrow` or `3 days`')

        if not status.hasTime:
            # replace it with the current time
            dt = dt.replace(hour=now.hour, minute=now.minute, second=now.second, microsecond=now.microsecond)

        self.dt = dt
        self._past = dt < now

    @classmethod
    async def convert(cls, ctx, argument):
        return cls(argument, now=ctx.message.created_at)


class Time(HumanTime):
    """Tries to convert to short time and then human time"""

    def __init__(self, argument, *, now=None):
        try:
            o = ShortTime(argument, now=now)
        except Exception as e:
            super().__init__(argument)
        else:
            self.dt = o.dt
            self._past = False


class FutureTime(Time):
    def __init__(self, argument, *, now=None):
        super().__init__(argument, now=now)

        if self._past:
            raise commands.BadArgument('This time is in the past')


class PastTime(Time):
    def __init__(self, argument, *, now=None):
        super().__init__(argument, now=now)
        if not self._past:
            raise commands.BadArgument('This time is in the future')


class UserFriendlyTime(commands.Converter):
    """That way quotes aren't absolutely necessary."""

    def __init__(self, converter=None, *, default=None, past=True, default_delta=None):
        if isinstance(converter, type) and issubclass(converter, commands.Converter):
            converter = converter()

        if converter is not None and not isinstance(converter, commands.Converter):
            raise TypeError('commands.Converter subclass necessary.')

        self.converter = converter
        self.default = default
        self.default_delta = default_delta
        self.dt = None
        self.arg = None
        self.past = past

    async def check_constraints(self, ctx, now, remaining):
        if self.past and self.dt > now:
            raise commands.BadArgument('This time is in the future.')

        if not self.past and self.dt < now:
            raise commands.BadArgument('This time is in the past.')

        if not remaining:
            if self.default is None:
                raise commands.BadArgument('Missing argument after the time.')
            remaining = self.default

        if self.converter is not None:
            self.arg = await self.converter.convert(ctx, remaining)
        else:
            self.arg = remaining
        return self

    def copy(self):
        cls = self.__class__
        obj = cls.__new__(cls)
        obj.converter = self.converter
        obj.default = self.default
        obj.past = self.past
        obj.default_delta = self.default_delta
        return obj

    async def convert(self, ctx, argument):
        # Create a copy of ourselves to prevent race conditions from two
        # events modifying the same instance of a converter
        result = self.copy()
        try:
            if result.past:
                calendar = HumanTime.past_calendar
            else:
                calendar = HumanTime.future_calendar
            regex = ShortTime.compiled
            now = ctx.message.created_at

            match = regex.match(argument)
            if match is not None and match.group(0):
                data = {k: int(v) for k, v in match.groupdict(default=0).items()}
                remaining = argument[match.end():].strip()
                result.dt = now + relativedelta(**data)
                if result.past and result.dt > now:
                    # Thinks it's in the future
                    result.dt = now - (result.dt - now)
                return await result.check_constraints(ctx, now, remaining)

            # apparently nlp does not like "from now"
            # it likes "from x" in other cases though so let me handle the 'now' case
            if argument.endswith('from now'):
                argument = argument[:-8].strip()

            if argument[0:2] == 'me':
                # starts with "me to", "me in", or "me at "
                if argument[0:6] in ('me to ', 'me in ', 'me at '):
                    argument = argument[6:]

            elements = calendar.nlp(argument, sourceTime=now)
            if elements is None or len(elements) == 0:
                if result.default_delta is not None:
                    result.dt = now + result.default_delta
                    return await result.check_constraints(ctx, now, argument)
                raise commands.BadArgument('Invalid time provided, try e.g. "tomorrow" or "3 days".')

            # handle the following cases:
            # "date time" foo
            # date time foo
            # foo date time

            # first the first two cases:
            dt, status, begin, end, dt_string = elements[0]

            if not status.hasDateOrTime:
                if result.default_delta is not None:
                    result.dt = now + result.default_delta
                    return await result.check_constraints(ctx, now, argument)
                raise commands.BadArgument('Invalid time provided, try e.g. "tomorrow" or "3 days".')

            if begin not in (0, 1) and end != len(argument):
                raise commands.BadArgument('Time is either in an inappropriate location, which '
                                           'must be either at the end or beginning of your input, '
                                           'or I just flat out did not understand what you meant. Sorry.')

            if not status.hasTime:
                # replace it with the current time
                dt = dt.replace(hour=now.hour, minute=now.minute, second=now.second, microsecond=now.microsecond)

            # if midnight is provided, just default to next day
            if status.accuracy == pdt.pdtContext.ACU_HALFDAY:
                dt = dt.replace(day=now.day + 1)

            result.dt = dt

            if begin in (0, 1):
                if begin == 1:
                    # check if it's quoted:
                    if argument[0] != '"':
                        raise commands.BadArgument('Expected quote before time input...')

                    if not (end < len(argument) and argument[end] == '"'):
                        raise commands.BadArgument('If the time is quoted, you must unquote it.')

                    remaining = argument[end + 1:].lstrip(' ,.!')
                else:
                    remaining = argument[end:].lstrip(' ,.!')
            elif len(argument) == end:
                remaining = argument[:begin].strip()
            if result.past and status.accuracy in (
                pdt.pdtContext.ACU_MONTH,
                pdt.pdtContext.ACU_WEEK,
                pdt.pdtContext.ACU_YEAR,
                pdt.pdtContext.ACU_DAY,
                pdt.pdtContext.ACU_HOUR,
                pdt.pdtContext.ACU_MIN,
                pdt.pdtContext.ACU_SEC,
                pdt.pdtContext.ACU_TIME
            ):
                result.dt = now - (result.dt - now)
            return await result.check_constraints(ctx, now, remaining)
        except Exception as e:
            if isinstance(e, commands.BadArgument):
                raise
            import traceback
            traceback.print_exc()
            raise


def human_timedelta(dt, *, source=None, accuracy=3, brief=False, suffix=True):
    now = source or datetime.datetime.utcnow()
    # Microsecond free zone
    now = now.replace(microsecond=0)
    dt = dt.replace(microsecond=0)

    # This implementation uses relativedelta instead of the much more obvious
    # divmod approach with seconds because the seconds approach is not entirely
    # accurate once you go over 1 week in terms of accuracy since you have to
    # hardcode a month as 30 or 31 days.
    # A query like "11 months" can be interpreted as "!1 months and 6 days"
    if dt > now:
        delta = relativedelta(dt, now)
        suffix = ''
    else:
        delta = relativedelta(now, dt)
        suffix = ' ago' if suffix else ''

    attrs = [
        ('year', 'y'),
        ('month', 'mo'),
        ('day', 'd'),
        ('hour', 'h'),
        ('minute', 'm'),
        ('second', 's'),
    ]

    output = []
    for attr, brief_attr in attrs:
        elem = getattr(delta, attr + 's')
        if not elem:
            continue

        if attr == 'day':
            weeks = delta.weeks
            if weeks:
                elem -= weeks * 7
                if not brief:
                    output.append(format(Plural(weeks), 'week'))
                else:
                    output.append(f'{weeks}w')

        if elem <= 0:
            continue

        if brief:
            output.append(f'{elem}{brief_attr}')
        else:
            output.append(format(Plural(elem), attr))

    if accuracy is not None:
        output = output[:accuracy]

    if len(output) == 0:
        return 'now'
    else:
        if not brief:
            return human_join(output, final='and') + suffix
        else:
            return ' '.join(output) + suffix
