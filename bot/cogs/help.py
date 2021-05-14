import discord
from discord.ext import commands, menus

from bot.util.paginator import Pages


class BotHelpPageSource(menus.ListPageSource):

    def __init__(self, help_command, cogs_commands):
        super().__init__(entries=sorted(cogs_commands.keys(), key=lambda c: c.qualified_name), per_page=5)
        self.help_command: HelpCommand = help_command
        self.cogs_commands: dict = cogs_commands

    # https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/meta.py#L41
    def short_cog(self, cog: commands.Cog, cogs_commands):
        if cog.description:
            description = cog.description.split("\n", 1)[0] + "\n"
        else:
            description = "No information...\n"

        count = len(description)
        end_note = "+{} others"
        end_length = len(end_note)

        page = []

        for command in cogs_commands:
            name = f"`{command.name}`"
            name_count = len(name) + 1
            if name_count + count < 800:
                count += name_count
                page.append(name)
            else:
                if count + end_length + 1 > 800:
                    page.pop()
                break

        if len(page) == len(cogs_commands):
            return description + ' '.join(page)

        left = len(cogs_commands) - len(page)
        return description + ' '.join(page) + "\n" + end_note.format(str(left))

    async def format_page(self, menu, cogs):
        top = f"`help [command/category]` for more specific help." \
              f"\n[Invite Me](https://youtube.com/)" \
              f" - [Support Server](https://discord.gg/WnaE3uZxDA) - [GitHub](https://github.com/DarkKronicle/Synth/)"

        embed = await create_embed(self.help_command, self.help_command.context.guild)
        description = ""

        for cog in cogs:
            cmds = self.cogs_commands.get(cog)
            if cmds:
                val = self.short_cog(cog, cmds)
                description += f"\n\n```\n{cog.qualified_name}\n```{val}"

        embed.description = top + description
        embed.set_author(name="Synth Help", url=self.help_command.context.bot.user.avatar_url)
        maximum = self.get_max_pages()
        if maximum > 1:
            embed.set_footer(text=f'Page {menu.current_page + 1}/{maximum} ({len(self.entries)} categories)')

        return embed


class GroupHelpPageSource(menus.ListPageSource):

    def __init__(self, help_command, group, commands, *, prefix):
        super().__init__(entries=commands, per_page=6)
        self.help_command = help_command
        self.group = group
        self.prefix = prefix
        self.title = f'{self.group.qualified_name} Commands'
        self.description = self.group.description

    async def format_page(self, menu, commands):
        embed = await create_embed(self.help_command, self.help_command.context.guild)
        description = self.description + "\n\n"
        for command in commands:
            signature = f'```\n{self.help_command.get_command_signature(command, show_aliases=False)}\n```'
            description += signature + (command.short_doc or 'No help given...')

        embed.description = description
        embed.title = self.title
        embed.set_author(name="Synth Help", url=self.help_command.context.bot.user.avatar_url)
        maximum = self.get_max_pages()
        if maximum > 1:
            embed.set_author(name=f'Page {menu.current_page + 1}/{maximum} ({len(self.entries)} commands)')

        return embed


class HelpMenu(Pages):

    def __init__(self, source):
        super().__init__(source)


async def create_embed(command, guild):
    prefix = ["s~"]
    if guild is None:
        prefix.append("~")
    else:
        prefix.append(await command.context.bot.get_guild_prefix(guild.id))
    embed = discord.Embed(colour=HelpCommand.MAIN_COLOR)
    embed.set_footer(text=f"Prefix: {', '.join(prefix)}")
    return embed


class HelpCommand(commands.HelpCommand):

    MAIN_COLOR = discord.Colour(0x9d0df0)

    def __init__(self):
        super().__init__(command_attrs={
            'help': 'Shows command information'
        })

    async def send_bot_help(self, mapping):
        bot = self.context.bot
        entries = await self.filter_commands(bot.commands, sort=True)
        all_commands = {}
        for command in entries:
            if command.cog is None:
                continue
            try:
                all_commands[command.cog].append(command)
            except KeyError:
                all_commands[command.cog] = [command]

        menu = HelpMenu(BotHelpPageSource(self, all_commands))
        await menu.start(self.context)

    def get_command_signature(self, command: commands.Command, *, show_aliases=True):
        parent = command.parent
        aliases = "|".join([command.name] + command.aliases)
        if parent is None:
            fmt = aliases
        else:
            parents_formatted = []
            while parent is not None:
                if show_aliases:
                    parents_formatted.append("|".join([parent.name] + parent.aliases))
                else:
                    parents_formatted.append(parent.name)
                parent = parent.parent
            fmt = f"{'|'.join(parents_formatted)} {aliases}"
        if len(command.signature) > 0:
            return f"{fmt} {command.signature}"
        return fmt

    async def send_group_help(self, group: commands.Group):
        subcommands = group.commands
        if len(subcommands) == 0:
            return await self.send_command_help(group)

        entries = await self.filter_commands(subcommands, sort=True)
        if len(entries) == 0:
            return await self.send_command_help(group)

        source = GroupHelpPageSource(self, group, entries, prefix=self.clean_prefix)
        menu = HelpMenu(source)
        await menu.start(self.context)

    def get_detailed_command(self, command: commands.Command):
        if command.help is not None:
            examples_split = command.help.split("Examples:")
            help_text = examples_split[0]
            if len(examples_split) > 1:
                examples = []
                for e in examples_split[1].split("\n")[1:]:
                    examples.append(e)
                if len(examples) > 0:
                    help_text += "Examples:```"
                    for e in examples:
                        e = e.replace('   ', '')
                        split = command.qualified_name.split(" ")
                        if len(split) > 1:
                            e = " ".join(split[:-1]) + e
                        help_text += f"\n{self.clean_prefix}{e}"
                    help_text += "\n```"
        else:
            help_text = "No help found..."
        return f"```\n{self.get_command_signature(command)}\n```\n{help_text}"

    async def send_command_help(self, command: commands.Command):
        embed = await create_embed(self, self.context.guild)
        embed.description = self.get_detailed_command(command)
        embed.title = f"{command.qualified_name}"
        embed.set_author(name="Synth Help", url=self.context.bot.user.avatar_url)
        await self.context.send(embed=embed)

    async def send_cog_help(self, cog):
        entries = await self.filter_commands(cog.get_commands(), sort=True)
        menu = HelpMenu(GroupHelpPageSource(self, cog, entries, prefix=self.clean_prefix))
        await menu.start(self.context)

