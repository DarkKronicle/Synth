from discord.ext import menus


class Pages(menus.MenuPages):

    def __init__(self, source, **kwargs):
        super().__init__(source, check_embeds=True, **kwargs)
