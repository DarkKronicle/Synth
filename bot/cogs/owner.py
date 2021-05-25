import discord
from bot import synth_bot
from discord.ext import commands


class Owner(commands.Cog):

    def __init__(self, bot):
        self.bot: synth_bot.SynthBot = bot
        self.degrees = 0

    async def cog_check(self, ctx):
        return await self.bot.is_owner(ctx.author)

    async def get_guild_embed(self, guild: discord.Guild, *, embed=None):
        if embed is None:
            embed = discord.Embed(title='Guild Information', colour=discord.Colour.purple())
        embed.add_field(
            name='Name/ID',
            value='{0} (ID: `{1}`'.format(guild.name, str(guild.id)),
        )
        embed.add_field(
            name='Owner',
            value='{0} (ID: `{1}`'.format(str(guild.owner), guild.owner.id),
        )
        total = guild.member_count
        bots = sum(member.bot for member in guild.members)
        text = 0
        voice = 0
        for channel in guild.channels:
            if isinstance(channel, discord.TextChannel):
                text = text + 1
            elif isinstance(channel, discord.VoiceChannel):
                voice = voice + 1
        message = 'Text Channels: `{text}`\nVoice Channels: `{voice}`\nTotal Channels: `{all}`\n\nMembers: `{members}`\nBots: `{bots}`'
        message = message.format(
            text=text,
            voice=voice,
            all=text + voice,
            members=total,
            bots=bots,
        )
        embed.description = message
        if guild.icon:
            embed.set_thumbnail(url=guild.icon_url)

        if guild.me:
            embed.timestamp = guild.me.joined_at

        return embed

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        embed = await self.get_guild_embed(
            guild,
            embed=discord.Embed(title='New Guild!', colour=discord.Colour.green()),
        )
        await self.bot.log.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        embed = await self.get_guild_embed(
            guild,
            embed=discord.Embed(title='Left Guild', colour=discord.Colour.red()),
        )
        await self.bot.log.send(embed=embed)


def setup(bot):
    bot.add_cog(Owner(bot))
