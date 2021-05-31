import enum
import discord


class FilterType(enum.Enum):

    guild = 0
    channel = 1
    user = 2
    role = 3
    category = 4

    @classmethod
    def from_object(cls, obj):
        if isinstance(obj, (discord.Guild,)):
            return FilterType.guild
        if isinstance(obj, (discord.VoiceChannel, discord.TextChannel, discord.StageChannel)):
            return FilterType.channel
        if isinstance(obj, (discord.User, discord.Member)):
            return FilterType.user
        if isinstance(obj, (discord.Role,)):
            return FilterType.role
        if isinstance(obj, (discord.CategoryChannel,)):
            return FilterType.category

    @classmethod
    def format_type(cls, obj):
        stat_type = FilterType.from_object(obj)
        if stat_type == FilterType.guild:
            return 'Guild {0}'.format(obj.name)
        if stat_type == FilterType.channel:
            return 'Channel {0}'.format(obj.mention)
        if stat_type == FilterType.user:
            return 'User {0}'.format(obj.mention)
        if stat_type == FilterType.role:
            return 'Role {0}'.format(obj.mention)
        if stat_type == FilterType.category:
            return 'Category {0}'.format(obj.name)
        return str(object)
