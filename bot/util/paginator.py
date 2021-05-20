import contextlib

import discord
from discord.ext import menus


class Pages(menus.MenuPages):

    def __init__(self, source, **kwargs):
        super().__init__(source, check_embeds=True, **kwargs)

    async def finalize(self, timed_out):
        with contextlib.suppress(discord.HTTPException):
            await self.message.clear_reactions()


class ImagePaginatorSource(menus.ListPageSource):

    def __init__(self, embed, images):
        super().__init__(images, per_page=1)
        self.embed: discord.Embed = embed
        self.images = images

    async def format_page(self, menu, page):
        maximum = self.get_max_pages()
        embed = self.embed.copy()
        if maximum > 1:
            embed.set_footer(
                text='Page {0}/{1} ({2} images)'.format(menu.current_page + 1, maximum, str(len(self.entries))),
            )
        embed.set_image(url='attachment://{0}'.format(page.filename))
        return {'embed': embed, 'file': page}


class ImagePaginator(Pages):

    def __init__(self, embed, images):
        self.images = images
        self.image_files = []
        for image_index, image in enumerate(self.images):
            self.image_files.append(discord.File(fp=image, filename='graph{0}.png'.format(image_index)))
        super().__init__(ImagePaginatorSource(embed, self.image_files))

    async def send_initial_message(self, ctx, channel):
        page = await self._source.get_page(self.current_page)
        kwargs = await self._get_kwargs_from_page(page)
        return await channel.send(**kwargs)

    async def show_page(self, page_number):
        self.current_page = page_number
        await self.message.delete()
        self.message = None
        await self.start(self.ctx)


class Prompt(menus.Menu):

    def __init__(self, starting_text, *, delete_after=True):
        super().__init__(check_embeds=True, delete_message_after=delete_after)
        self.starting_text = starting_text
        self.result = None

    async def send_initial_message(self, ctx, channel):
        embed = ctx.create_embed(self.starting_text)
        return await ctx.send(embed=embed)

    async def start(self, ctx, *, channel=None, wait=None):
        if wait is None:
            wait = True
        return await super().start(ctx, channel=channel, wait=wait)

    @menus.button('\N{WHITE HEAVY CHECK MARK}')
    async def confirm(self, payload):
        self.result = True
        self.stop()

    @menus.button('\N{CROSS MARK}')
    async def do_deny(self, payload):
        self.result = False
        self.stop()
