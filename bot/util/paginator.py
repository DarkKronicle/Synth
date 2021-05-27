import contextlib
import io

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
        self.continued = False


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


class SimplePageSource(menus.ListPageSource):

    def __init__(self, entries, *, per_page=15):
        super().__init__(entries, per_page=per_page)

    async def format_page(self, menu, entries):
        pages = []
        if self.per_page > 1:
            for index, entry in enumerate(entries, start=menu.current_page * self.per_page):
                pages.append(f"**{index + 1}.** {entry}")
        else:
            pages.append(f"**{menu.current_page + 1}.** {entries}")

        maximum = self.get_max_pages()
        if maximum > 1:
            footer = f"Page {menu.current_page + 1}/{maximum} ({len(self.entries)} entries.)"
            menu.embed.set_footer(text=footer)

        menu.embed.description = '\n'.join(pages)
        return menu.embed


class SimplePages(Pages):

    def __init__(self, entries, *, per_page=10, embed=discord.Embed(colour=discord.Colour.purple())):
        super().__init__(SimplePageSource(entries, per_page=per_page))
        self.embed = embed
        self.entries = entries
