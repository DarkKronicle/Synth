import typing
from datetime import datetime

import discord

from bot.util import paginator
from bot.util.context import Context
from dateutil.tz import gettz
from discord.ext import commands


class ZoneConverter(commands.Converter):

    async def convert(self, ctx, argument):
        if not argument:
            raise commands.BadArgument('Invalid time zone!')
        zone = gettz(argument)
        if zone is None:
            raise commands.BadArgument('Invalid time zone!')
        return zone


class Utility(commands.Cog):
    """Miscellaneous utility commands."""

    utc = gettz('UTC')

    @commands.command(name='ping')
    async def ping(self, ctx):
        """
        Pings the bot and gets the millisecond delay.
        """
        time0 = ctx.message.created_at
        sent = await ctx.send('Pinging')
        time1 = sent.created_at
        dif1 = round((time1 - time0).total_seconds() * 1000)
        await sent.edit(content='Pong! Pinging time was {0}ms'.format(dif1))

    @commands.command(name='zoneconverter', aliases=['zone2zone', 'z2z'])
    async def time_convert(
        self,
        ctx: Context,
        from_zone: typing.Optional[ZoneConverter],
        to_zone: ZoneConverter = None,
    ):
        """
        Converts one time zone to another time zone. Default [from_zone] is UTC.

        Examples:
              z2z EST
              z2z EST MST
        """
        # Fixing converter optionals
        if to_zone is None:
            to_zone = from_zone
            from_zone = None
        if from_zone is None:
            from_zone = self.utc
        from_current_time = datetime.now(from_zone)
        to_current_time = from_current_time.astimezone(to_zone)
        f_form = from_current_time.strftime('%H:%M:%S %z')
        t_form = to_current_time.strftime('%H:%M:%S %z')
        await ctx.send(embed=ctx.create_embed(
            description='From:\n `{0}`\n\nTo:\n `{1}`'.format(f_form, t_form),
            title='{0} -> {1}'.format(from_current_time.tzname(), to_current_time.tzname()),
        ))

    @commands.command(name='user')
    async def user(self, ctx: Context, user: discord.Member = None):
        """
        Get's information about a user.

        Examples:
            user
            user DarkKronicle
        """
        if user is None:
            user = ctx.author
        pfp = user.avatar_url
        embed = ctx.create_embed(title=str(user))
        embed.set_image(url=pfp)
        description = 'Created: `{0.created_at}`'.format(user)
        embed.description = description
        await ctx.send(embed=embed)

    @commands.command(name='poll')
    async def poll(self, ctx: Context, *, channel: typing.Optional[discord.TextChannel]):
        """Creates a setup wizard for polls."""
        if channel is not None:
            if not channel.permissions_for(ctx.author).send_messages:
                return await ctx.send(
                    embed=ctx.create_embed(
                        "You aren't allowed to send messages in <#{0allowed to send messages in <#{0}>".format(channel.id),
                        error=True,
                    ),
                )
        if channel is None:
            channel = ctx.channel
        title = await ctx.ask(embed=ctx.create_embed('What will the title for the poll be?'))
        if not title:
            return await ctx.send(embed=ctx.create_embed('Timed out!', error=True))
        description = await ctx.ask(embed=ctx.create_embed('What will the description for the poll be?'))
        if not description:
            return await ctx.send(embed=ctx.create_embed('Timed out!', error=True))
        options = []
        i = 0
        while True:
            i += 1
            emoji = await ctx.reaction(embed=ctx.create_embed('What emoji will this option have?\n\nReact with it!', title='Option {0}'.format(i)))
            if not emoji:
                return await ctx.send(embed=ctx.create_embed('Timed out!', error=True))
            question = await ctx.ask(
                embed=ctx.create_embed('What will the option be?', title='Option {0}'.format(i)),
                timeout=180,
            )
            if not description:
                return await ctx.send(embed=ctx.create_embed('Timed out!', error=True))
            options.append((emoji, question))
            if i > 7:
                break
            prompt = paginator.Prompt('Add another option?')
            try:
                await prompt.start(ctx)
            except:
                return await ctx.send(embed=ctx.create_embed('An error occured in the menu!', error=True))
            if not prompt.result:
                break
        max_len = 1800
        length = 0
        elements = []
        for emoji, question in options:
            val = '{0} - {1}'.format(str(emoji), question)
            length += len(val)
            if length > max_len:
                break
            elements.append(val)
        embed = await channel.send(
            embed=ctx.create_embed(title=title, description='{0}\n\n{1}'.format(description, '\n'.join(elements)))
        )
        for emoji, _ in options:
            await embed.add_reaction(emoji)

    @commands.command(name='roles')
    @commands.guild_only()
    async def roles(self, ctx: Context, user: typing.Optional[discord.Member] = None):
        """
        Displays the roles a user has.

        Examples:
            roles @DarkKronicle
            roles Fury
            roles
        """
        if not user:
            user = ctx.author
        entries = []
        for role in user.roles:
            role: discord.Role
            entries.append('{0}\n```\n  Colour: {2}\n  Members: {3}\n  id {1}\n```'
                           .format(role.mention, role.id, str(role.colour), len(role.members)))
        page = paginator.SimplePages(entries, embed=ctx.create_embed(title='Roles for {0}'.format(str(user))), per_page=5)
        try:
            await page.start(ctx)
        except:
            pass


def setup(bot):
    bot.add_cog(Utility())
