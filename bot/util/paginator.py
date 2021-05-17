import discord
from discord.ext import menus


class Pages(menus.MenuPages):

    def __init__(self, source, **kwargs):
        super().__init__(source, check_embeds=True, **kwargs)

    async def finalize(self, timed_out):
        try:
            await self.message.clear_reactions()
        except discord.HTTPException:
            pass


class ImagePaginatorSource(menus.ListPageSource):

    def __init__(self, embed, images):
        super().__init__(images, per_page=1)
        self.embed: discord.Embed = embed
        self.images = images

    async def format_page(self, menu, page):
        maximum = self.get_max_pages()
        embed = self.embed.copy()
        if maximum > 1:
            embed.set_footer(text=f'Page {menu.current_page + 1}/{maximum} ({len(self.entries)} images)')
        embed.set_image(url=f'attachment://{page.filename}')
        return {'embed': embed, 'file': page}


class ImagePaginator(Pages):

    def __init__(self, embed, images):
        self.images = images
        self.files = []
        f = 0
        for i in self.images:
            self.files.append(discord.File(fp=i, filename=f'graph{f}.png'))
            f += 1
        super().__init__(ImagePaginatorSource(embed, self.files))

    async def send_initial_message(self, ctx, channel):
        page = await self._source.get_page(self.current_page)
        kwargs = await self._get_kwargs_from_page(page)

        # kwargs['files'] = files
        return await channel.send(**kwargs)

    async def show_page(self, page_number):
        self.current_page = page_number
        await self.message.delete()
        self.message = None
        await self.start(self.ctx)


