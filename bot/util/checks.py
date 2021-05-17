from discord.ext import commands


# https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/utils/checks.py#L11
# MPL-2.0
async def check_permissions(ctx, perms, *, check=all, channel=None):
    is_owner = await ctx.bot.is_owner(ctx.author)
    if is_owner:
        return True

    if channel is None:
        channel = ctx.channel
    resolved = channel.permissions_for(ctx.author)
    perms_given = []
    for name, perm in perms.items():
        perms_given.append(getattr(resolved, name, None) == perm)
    return check(perms_given)


async def check_guild_permissions(ctx, perms, *, check=all):
    is_owner = await ctx.bot.is_owner(ctx.author)
    if is_owner:
        return True

    if ctx.guild is None:
        return True

    resolved = ctx.author.guild_permissions
    perms_given = []
    for name, perm in perms.items():
        perms_given.append(getattr(resolved, name, None) == perm)
    return check(perms_given)


def is_admin():
    async def predicate(ctx):   # noqa: WPS430
        return await check_guild_permissions(ctx, {'administrator': True})

    return commands.check(predicate)


def is_mod():
    async def predicate(ctx):   # noqa: WPS430
        return await check_guild_permissions(ctx, {'manage_server': True, 'administrator': True}, check=any)

    return commands.check(predicate)


def guild(*args):
    async def predicate(ctx):   # noqa: WPS430
        if ctx.guild is None:
            return False
        return ctx.guild.id in args

    return commands.check(predicate)


def owner_or(*args):
    async def predicate(ctx):   # noqa: WPS430
        if ctx.author.id in args:
            return True
        return await ctx.bot.is_owner(ctx.author)

    return commands.check(predicate)
