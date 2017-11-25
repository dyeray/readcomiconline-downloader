import asyncio
import logging
import os
import sys
import urllib.parse as urlparse
from contextlib import closing

import aiofiles
import aiohttp
import structlog
from arsenic import browsers, services, get_session


CHUNK_SIZE = 4 * 1024 # 4 KB


logging.basicConfig(level=logging.CRITICAL+10)
structlog.configure(logger_factory=structlog.stdlib.LoggerFactory())


async def download_image(session, name, url):
    async with session.get(url) as response:
        filetype = response.headers['Content-Type'].split('/')[-1]
        async with aiofiles.open(f'{name}.{filetype}', 'wb') as f:
            while True:
                chunk = await response.content.read(CHUNK_SIZE)
                if not chunk:
                    break
                await f.write(chunk)


async def download_images(links):
    with aiohttp.ClientSession() as session:
        await asyncio.wait([download_image(session, idx, link) for idx, link in enumerate(links)])


async def clean_url(url):
    parsed_url = urlparse.urlparse(url)
    query_params = {
        **urlparse.parse_qs(parsed_url.query),
        'quality': ['hq'],
        'readType': ['1']
    }
    new_parsed_url = parsed_url._replace(query=urlparse.urlencode(query_params, doseq=True))
    return new_parsed_url.geturl()

async def parse_comic(url):
    url = await clean_url(url)
    async with get_session(services.PhantomJS(log_file=os.devnull),
                           browsers.PhantomJS(loadImages=False)) as session:
        await session.get(url)
        await session.wait_for_element(15, '#containerRoot')
        image_links = await session.execute_script('return lstImages')
    await download_images(image_links)


def download_comic(url):
    with closing(asyncio.get_event_loop()) as loop:
        loop.run_until_complete(parse_comic(url))

if __name__ == '__main__':
    download_comic(sys.argv[1])
