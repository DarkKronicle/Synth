from discord.ext import commands
import random
import json


with open('data/emojis.json', 'r') as file:
    all_emojis: dict = json.load(file)


emoji_list = []

for _, emoji in all_emojis.items():
    diversity = emoji.get("diversity")
    if diversity is None:
        emoji_list.append(emoji["emoji"])
    else:
        emoji_list.extend([e for _, e in emoji["diversity"].items()])

all_emoji_data: dict = {k: v["emoji"] for k, v in all_emojis.items()}


class StandardEmoji(commands.Converter):
    async def convert(self, ctx, argument):
        """
        # 1 - Check if unicode emoji
        # 2 - Check if it's name is in discord found
        """

        if argument in all_emoji_data.values():
            return argument

        argument = argument.lower()
        if argument in all_emoji_data.keys():
            return all_emoji_data[argument]

        return None


class Emoji(commands.Converter):
    async def convert(self, ctx, argument):
        discord_convert = commands.EmojiConverter()
        try:
            e = await discord_convert.convert(ctx, argument)
        except commands.EmojiNotFound:
            e = None
        if e is not None:
            return e
        standard_convert = StandardEmoji()
        e = await standard_convert.convert(ctx, argument)
        if e is None:
            raise commands.EmojiNotFound(argument)
        return e


async def random_reaction(message=None):
    emojis = random.choice(emoji_list)
    if message:
        try:
            await message.add_reaction(emojis)
        except:
            pass
    return emojis
