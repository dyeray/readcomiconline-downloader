import asyncio
import logging
import os
import sys
import tempfile
import urllib.parse as urlparse
from contextlib import closing
from glob import glob
from typing import List
from zipfile import ZipFile

import aiofiles
import aiohttp
import structlog
from arsenic import browsers, services, get_session


CHUNK_SIZE = 4 * 1024  # 4 KB


# Disable arsenic logging.
logging.basicConfig(level=logging.CRITICAL+10)
structlog.configure(logger_factory=structlog.stdlib.LoggerFactory())


async def download_file(session: aiohttp.ClientSession, name, url: str, directory: str):
    """Download a file from a url."""
    async with session.get(url) as response:
        filetype = response.headers['Content-Type'].split('/')[-1]
        async with aiofiles.open(os.path.join(directory, f'{name}.{filetype}'), 'wb') as f:
            while True:
                chunk = await response.content.read(CHUNK_SIZE)
                if not chunk:
                    break
                await f.write(chunk)


async def download_files(links: List[str], directory: str):
    """Download files from a list of urls."""
    async with aiohttp.ClientSession() as session:
        await asyncio.wait([download_file(session, str(idx).zfill(3), link, directory)
                            for idx, link in enumerate(links)])


async def clean_url(url: str) -> str:
    """Process a ReadComicOnline.to URL to make sure the page will be parsed correctly."""
    parsed_url = urlparse.urlparse(url)
    query_params = {
        **urlparse.parse_qs(parsed_url.query),
        'quality': ['hq'],
        'readType': ['1']
    }
    new_parsed_url = parsed_url._replace(query=urlparse.urlencode(query_params, doseq=True))
    return new_parsed_url.geturl()


async def create_comic_book(name: str, input_dir: str):
    """Create a CBZ file from the files of an input directory."""
    def _create_comic_book(input_dir: str):
        with ZipFile(f'{name}.cbz', 'w') as zip_file:
            for filename in glob(os.path.join(input_dir, '*')):
                zip_file.write(filename, os.path.basename(filename))

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _create_comic_book, input_dir)


async def download_comic(url: str):
    """Download a comic from a ReadComicOnline.to url."""
    url = await clean_url(url)
    async with get_session(services.PhantomJS(log_file=os.devnull),
                           browsers.PhantomJS(loadImages=False)) as session:
        await session.get(url)
        await session.wait_for_element(15, '#containerRoot')
        image_links = await session.execute_script('return lstImages')
        title = await session.execute_script('return document.title')
    with tempfile.TemporaryDirectory() as tempdir:
        await download_files(image_links, tempdir)
        await create_comic_book(title.split(' - ')[0].strip(), tempdir)


if __name__ == '__main__':
    with closing(asyncio.get_event_loop()) as loop:
        loop.run_until_complete(download_comic(sys.argv[1]))
