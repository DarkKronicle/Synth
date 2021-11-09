import contextlib
import io

import discord
from discord.ext import menus
from glocklib.paginator import Pages


class ImagePaginatorSource(menus.ListPageSource):

    def __init__(self, embed, images):
        super().__init__(images, per_page=1)
        self.embed: discord.Embed = embed
        self.images = images

    async def format_page(self, menu, page):
        image, fp = page
        maximum = self.get_max_pages()
        embed = self.embed.copy()
        if maximum > 1:
            embed.set_footer(
                text='Page {0}/{1} ({2} images)'.format(menu.current_page + 1, maximum, str(len(self.entries))),
            )
        embed.set_image(url='attachment://{0}'.format(image.filename))
        # Make sure we're good to read
        image.fp = io.BytesIO(fp.read())
        fp.seek(0)
        image.fp.seek(0)
        return {'embed': embed, 'file': image}

    async def finalize(self, time_out):
        for image, fp in self.images:
            image.fp.close()
            fp.close()


class ImagePaginator(Pages):

    def __init__(self, embed, images):
        self.images = images
        self.image_files = []
        self.continued = False
        for image_index, image in enumerate(self.images):
            self.image_files.append((discord.File(fp=image, filename='graph{0}.png'.format(image_index)), image))
        super().__init__(ImagePaginatorSource(embed, self.image_files))

    async def send_initial_message(self, ctx, channel):
        page = await self._source.get_page(self.current_page)
        kwargs = await self._get_kwargs_from_page(page)
        return await channel.send(**kwargs)

    async def show_page(self, page_number):
        self.current_page = page_number
        await self.message.delete()
        self.message = None
        self.continued = True
        await self.start(self.ctx)

    async def start(self, ctx, *, channel=None, wait=False):
        await super().start(ctx, channel=channel, wait=wait)

    async def finalize(self, timed_out):
        if not self.continued:
            await self.source.finalize(timed_out)
        await super().finalize(timed_out)

