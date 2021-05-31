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


async def get_command_config(ctx):
    cog = ctx.bot.get_config('CommandSettings')
    if cog is None:
        return None
    return await cog.get_command_config(ctx.guild.id)


async def raw_is_admin(ctx):
    if ctx.guild is None:
        return True
    allowed = await check_guild_permissions(ctx, {'administrator': True})
    if allowed:
        return allowed
    config = await get_command_config(ctx)
    if not config:
        return False
    admin_id = config.admin_id
    for role in ctx.author.roles:
        if role.id == admin_id:
            return True
    return False


def is_admin():
    async def predicate(ctx):   # noqa: WPS430
        return await check_guild_permissions(ctx, {'administrator': True})

    return commands.check(predicate)


def is_manager():
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
