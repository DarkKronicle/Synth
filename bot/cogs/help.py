import discord
from bot.util.paginator import Pages
from discord.ext import commands, menus


COG_LENGTH = 800
MAIN_COLOR = discord.Colour(0x9D0DF0)  # noqa: WPS432


class BotHelpPageSource(menus.ListPageSource):

    def __init__(self, help_command, cogs_commands):
        entries = sorted(cogs_commands.keys(), key=lambda command: command.qualified_name)
        super().__init__(entries=entries, per_page=5)
        self.help_command: HelpCommand = help_command
        self.cogs_commands: dict = cogs_commands

    # https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/meta.py#L41
    def short_cog(self, cog: commands.Cog, cogs_commands):
        if cog.description:
            description = '{0}\n'.format(cog.description.split('\n', 1)[0])
        else:
            description = 'No information...\n'

        count = len(description)
        end_note = '+{0} others'
        end_length = len(end_note)

        page = []

        for command in cogs_commands:
            name = '`{0}`'.format(command.name)
            name_count = len(name) + 1
            if name_count + count < COG_LENGTH:
                count += name_count
                page.append(name)
            else:
                if count + end_length + 1 > COG_LENGTH:
                    page.pop()
                break

        if len(page) == len(cogs_commands):
            return description + ' '.join(page)

        left = len(cogs_commands) - len(page)
        end_note = end_note.format(str(left))
        return '{0}{1}\n{2}'.format(description, ' '.join(page), end_note)

    async def format_page(self, menu, cogs):
        top = """
            `help [command/category]` for more specific help.'
            [Invite Me](https://youtube.com/)
            - [Support Server](https://discord.gg/WnaE3uZxDA) - [GitHub](https://github.com/DarkKronicle/Synth/)
        """
        top = top.replace('    ', '')

        embed = await create_embed(self.help_command, self.help_command.context.guild)
        description = ''

        for cog in cogs:
            cog_commands = self.cogs_commands.get(cog)
            if cog_commands:
                cog_description = self.short_cog(cog, cog_commands)
                description += '\n\n```\n{0}\n```{1}'.format(cog.qualified_name, cog_description)

        embed.description = top + description
        context = self.help_command.context
        embed.set_author(name='Synth Help', url=context.bot.user.avatar_url)
        maximum = self.get_max_pages()
        if maximum > 1:
            footer = 'Page {0}/{1} ({2} categories)'.format(menu.current_page + 1, maximum, len(self.entries))
            embed.set_footer(text=footer)

        return embed


class GroupHelpPageSource(menus.ListPageSource):

    def __init__(self, help_command, group, group_commands, *, prefix):
        super().__init__(entries=group_commands, per_page=6)
        self.help_command = help_command
        self.group = group
        self.prefix = prefix
        self.title = '{0} Commands'.format(self.group.qualified_name)
        self.description = self.group.description

    async def format_page(self, menu, group_commands):
        embed = await create_embed(self.help_command, self.help_command.context.guild)
        description = '{0}\n\n'.format(self.description)
        for command in group_commands:
            signature = self.help_command.get_command_signature(command, show_aliases=False)
            signature = '```\n{0}\n```'.format(signature)
            description += signature + (command.short_doc or 'No help given...')

        embed.description = description
        embed.title = self.title
        bot = self.help_command.context.bot
        embed.set_author(name='Synth Help', url=bot.user.avatar_url)
        maximum = self.get_max_pages()
        if maximum > 1:
            footer = 'Page {0}/{1} ({2} commands)'.format(menu.current_page + 1, maximum, len(self.entries))
            embed.set_footer(text=footer)

        return embed


class HelpMenu(Pages):
    """Specific menu for help."""


async def create_embed(command, guild):
    prefix = ['s~']
    if guild is None:
        prefix.append('~')
    else:
        prefix.append(await command.context.bot.get_guild_prefix(guild.id))
    embed = discord.Embed(colour=HelpCommand.MAIN_COLOR)
    embed.set_footer(text='Prefix: {0}'.format(', '.join(prefix)))
    return embed


class HelpCommand(commands.HelpCommand):

    def __init__(self):
        super().__init__(command_attrs={
            'help': 'Shows command information',
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
        aliases = '|'.join([command.name] + command.aliases)
        if parent is None:
            fmt = aliases
        else:
            parents_formatted = []
            while parent is not None:
                if show_aliases:
                    parents_formatted.append('|'.join([parent.name] + parent.aliases))
                else:
                    parents_formatted.append(parent.name)
                parent = parent.parent
            fmt = '|'.join(parents_formatted) + aliases
        if command.signature:
            return '{0} {1}'.format(fmt, command.signature)
        return fmt

    async def send_group_help(self, group: commands.Group):
        subcommands = group.commands
        if not subcommands:
            return await self.send_command_help(group)

        entries = await self.filter_commands(subcommands, sort=True)
        if not entries:
            return await self.send_command_help(group)

        source = GroupHelpPageSource(self, group, entries, prefix=self.clean_prefix)
        menu = HelpMenu(source)
        await menu.start(self.context)

    def get_examples(self, examples, command):
        help_text = 'Examples:```'
        for example in examples:
            example = example.replace('   ', '')
            split = command.qualified_name.split(' ')
            if len(split) > 1:
                example = ' '.join(split[:-1]) + example
            help_text += '\n{0}{1}'.format(self.clean_prefix, example)
        return '{0}\n```'.format(help_text)

    def get_detailed_command(self, command: commands.Command):
        if command.help is not None:
            examples_split = command.help.split('Examples:')
            help_text = examples_split[0]
            if len(examples_split) > 1:
                examples = []
                for example in examples_split[1].split('\n')[1:]:
                    examples.append(example)
                if examples:
                    help_text = help_text + self.get_examples(examples, command)
        else:
            help_text = 'No help found...'
        return '```\n{0}\n```\n{1}'.format(self.get_command_signature(command), help_text)

    async def send_command_help(self, command: commands.Command):
        embed = await create_embed(self, self.context.guild)
        embed.description = self.get_detailed_command(command)
        embed.title = command.qualified_name
        embed.set_author(name='Synth Help', url=self.context.bot.user.avatar_url)
        await self.context.send(embed=embed)

    async def send_cog_help(self, cog):
        entries = await self.filter_commands(cog.get_commands(), sort=True)
        menu = HelpMenu(GroupHelpPageSource(self, cog, entries, prefix=self.clean_prefix))
        await menu.start(self.context)
