import seaborn as sns
from matplotlib import pyplot as plt
from matplotlib import dates as md
from io import BytesIO
from datetime import datetime, timedelta, date
from collections import Counter, OrderedDict
from bot.util import time_util as tutil
from bot.synth_bot import main_color
import random
import pandas as pd


def lock_24_hours(entries, *, time=False):
    data = Counter()
    min_date = datetime.now()
    max_date = datetime.now() - timedelta(hours=1)
    for e in entries:
        if e['channel_id'] is None and e['user_id'] is None:
            continue
        elif e['channel_id'] is None and e['user_id'] is not None:
            continue
        min_date = min(min_date, e['time'])
        max_date = max(max_date, e['time'])
        if time:
            data[e['time']] += e['amount'].total_seconds()
        else:
            data[e['time']] += e['amount']
    if (max_date - min_date).days > 0:
        days = True
        keys = [k for k in data.keys()]
        for k in keys:
            data[datetime.combine(date.min, k.time()) - datetime.min] = data.pop(k)
        min_date = timedelta(days=0)
        data[min_date] = 0
        max_date = timedelta(days=1)
        data[max_date] = 0
    else:
        days = False
        keys = [k for k in data.keys()]
        for k in keys:
            data[datetime.combine(date.min, k.time()) - datetime.min] = data.pop(k)
        max_date = timedelta(days=1)
        min_date = timedelta(days=0)
        data[max_date] = 0
        data[min_date] = 0
    return data, min_date, max_date, days


def plot_24_hour_messages(entries):
    # Amount of messages per time
    data, min_date, max_date, days = lock_24_hours(entries)
    y = []
    for d, amount in data.items():
        y.extend([d.total_seconds() // (60 * 60)] * amount)
    if days:
        y.sort()
    sns.set_theme(style="ticks", context="paper")
    plt.style.use("dark_background")
    plt.figure()
    random.seed(len(entries))
    strip = [random.uniform(-.5, .5) + i for i in y]
    random.seed()
    ax = sns.swarmplot(x=strip, color='.2', alpha=0.9, size=3)
    ax = sns.violinplot(x=y, inner=None, palette='Blues')
    ax.set_xlim(min_date.total_seconds() // (60 * 60), max_date.total_seconds() // (60 * 60))
    utc = tutil.get_utc()
    ax.set_xticks([i for i in range(24)])
    ax.set_xticklabels(['{0}:00'.format(i) for i in range(24)])
    ax.tick_params(axis="x", rotation=45)
    ax.text(utc.hour + (utc.minute / 60), 0.47, 'Now')

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)

    buffer = BytesIO()
    plt.savefig(buffer, format='png', transparent=True, bbox_inches='tight')
    plt.clf()
    plt.close()
    buffer.seek(0)
    return buffer


def plot_week_messages(entries):
    # Amount of messages per time
    min_date = datetime.now()
    max_date = datetime.now() - timedelta(hours=1)
    now = datetime.now().date()
    data = []
    order_data = {}
    for e in entries:
        if e['channel_id'] is None and e['user_id'] is None:
            continue
        elif e['channel_id'] is None and e['user_id'] is not None:
            continue
        days = (now - e['time'].date()).days
        if days > 7:
            continue
        min_date = min(min_date, e['time'])
        max_date = max(max_date, e['time'])
        order_data[days] = e['time'].strftime('%A')
        for i in range(e['amount']):
            data.append((
                e['time'].strftime('%A'),
                (datetime.combine(date.min, e['time'].time()) - datetime.min).total_seconds(),
            ))
    order = [v for i, v in sorted(order_data.items(), key=lambda item: item[0], reverse=True)]
    df = pd.DataFrame(data, columns=['Days', 'Amount'])

    diff = (max_date - min_date).days
    if diff < 2:
        return None

    min_date = timedelta(days=0)
    max_date = timedelta(days=1)

    sns.set_theme(style="ticks", context="paper")
    plt.style.use("dark_background")
    plt.figure()
    ax = sns.violinplot(y='Days', x='Amount', data=df, inner='stick', palette='Blues', order=order, scale_hue=False, scale='count')
    ax.set_xlim(min_date.total_seconds(), max_date.total_seconds())
    now = tutil.get_utc()
    ax.set_xticks([3600 * i for i in range(24)] + [now.hour / 60])
    ax.set_xticklabels(['{0}:00'.format(i) for i in range(24)] + ['Now'])
    ax.tick_params(axis='x', rotation=45)

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)

    buffer = BytesIO()
    plt.savefig(buffer, format='png', transparent=True, bbox_inches='tight')
    plt.clf()
    plt.close()
    buffer.seek(0)
    return buffer


def plot_daily_message(entries):
    messages = Counter()
    names = {}
    now = tutil.get_utc().date()
    max_days = 0
    for e in entries:
        days = -1 * (now - e['time'].date()).days
        if e['channel_id'] is None and e['user_id'] is None:
            messages[days] += e['amount']
        elif e['user_id'] is not None:
            messages[days] += e['amount']
        else:
            continue

        max_days = max(max_days, days * -1)
    if max_days < 3:
        return None
    x = []
    y = []
    for day in range(max_days + 1):
        day = day - max_days
        val = messages[day]
        x.append(day)
        y.append(val)
        if day not in names:
            names[day] = (now + timedelta(days=day)).strftime('%m/%d')
    print(x)
    print(y)
    sns.set_theme(style="ticks", context="paper")
    plt.style.use("dark_background")
    plt.figure()
    ax = sns.lineplot(x=x, y=y)
    ax.set_xlim(max_days * -1, 0)
    ax.set_xticks([i - max_days for i in range(max_days + 1)])
    ax.set_xticklabels([display for days, display in sorted(names.items(), key=lambda item: item[0])])
    ax.tick_params(axis='x', rotation=45)

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    buffer = BytesIO()
    plt.savefig(buffer, format='png', transparent=True, bbox_inches='tight')
    plt.clf()
    plt.close()
    buffer.seek(0)
    return buffer


def plot_message_channel_bar(ctx, entries):
    lost = 0
    channels = Counter()
    id_to_name = {}
    for e in entries:
        channel_id = e['channel_id']
        if channel_id is None and e['user_id'] is None:
            lost += e['amount']
        elif channel_id is not None:
            if channel_id not in id_to_name:
                channel = ctx.guild.get_channel(channel_id)
                if channel is not None:
                    id_to_name[channel_id] = channel.name
                else:
                    id_to_name[channel_id] = str(channel_id)
            channels[id_to_name[channel_id]] += e['amount']
    return plot_bar(channels)


def plot_bar(values):
    name = []
    amount = []
    i = 0
    other = 0
    for c, a in sorted(values.items(), key=lambda item: item[1], reverse=True):
        if i >= 9:
            other += a
            continue
        name.append(c)
        amount.append(a)
        i += 1
    if other > 0:
        name.append('Other...')
        amount.append(other)

    labels = name
    sizes = amount
    plt.style.use('dark_background')
    sns.set_theme(style="ticks", context="talk")
    plt.style.use("dark_background")
    plt.figure()
    ax = sns.barplot(x=sizes, y=labels, palette='Blues')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    buffer = BytesIO()
    plt.savefig(buffer, format='png', transparent=True, bbox_inches='tight')
    buffer.seek(0)
    plt.clf()
    plt.close()

    return buffer


def plot_message_user_bar(ctx, entries):
    lost = 0
    users = Counter()
    id_to_name = {}
    for e in entries:
        user_id = e['user_id']
        if user_id is None and e['channel_id'] is None:
            lost += e['amount']
        elif user_id is not None:
            if user_id not in id_to_name:
                user = ctx.guild.get_member(user_id)
                if user is not None:
                    id_to_name[user_id] = user.name
                else:
                    id_to_name[user_id] = str(user_id)
            users[id_to_name[user_id]] += e['amount']
    return plot_bar(users)


def plot_24_hour_voice(entries):
    data = Counter()
    logged = {}
    min_date = datetime.now()
    max_date = datetime.now() - timedelta(hours=1)
    data[datetime.now()] = 0
    data[datetime.now() - timedelta(days=1)] = 0
    for e in entries:
        time = tutil.round_time(e['time'], 60 * 30)
        added = 0
        min_date = min(min_date, e['time'])
        while added < e['amount'].total_seconds():
            max_date = max(max_date, time)
            if time not in logged:
                logged[time] = []
            if e['user_id'] not in logged[time]:
                data[time] += 1
                logged[time].append(e['user_id'])
            time = time + timedelta(minutes=30)
            added += 60 * 30
    if (max_date - min_date).days > 0:
        keys = [k for k in data.keys()]
        for k in keys:
            data[k.replace(year=2020, month=1, day=1)] = data.pop(k)
        min_date = datetime(year=2020, month=1, day=1, minute=0, hour=0, second=0, microsecond=0)
        data[min_date] = 0
        max_date = datetime(year=2020, month=1, day=2, minute=0, hour=0, second=0, microsecond=0)
        data[max_date] = 0
    else:
        max_date = tutil.get_utc() + timedelta(minutes=30)
        min_date = max_date - timedelta(days=1, minutes=30)
        data[max_date] = 0
        data[min_date] = 0
    plt.style.use('dark_background')
    fig, ax = plt.subplots(ncols=1, nrows=1)
    ax.xaxis.set_major_locator(md.HourLocator(interval=2))
    ax.xaxis.set_minor_locator(md.HourLocator(interval=1))
    date_fm = md.DateFormatter('%H:%M')
    ax.xaxis.set_major_formatter(date_fm)
    ax.yaxis.grid(color='white', alpha=0.2)

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)

    ax.set_xlabel('Time (UTC)')
    ax.set_ylabel('Amount in Voice Channel')
    _ = ax.bar(data.keys(), data.values(), width=1 / 48, alpha=1, align='edge', edgecolor=str(main_color),
               color=str(main_color))
    fig.autofmt_xdate()

    plt.xlim([min_date, max_date])
    buffer = BytesIO()
    fig.savefig(buffer, format='png', transparent=True, bbox_inches='tight')
    buffer.seek(0)
    fig.clear()
    plt.close(fig)
    return buffer
