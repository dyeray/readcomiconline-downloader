import asyncio
import os
import re
import tempfile
import urllib.parse as urlparse
from contextlib import closing
from glob import glob
from typing import List, Tuple
from zipfile import ZipFile

import aiofiles
import aiohttp
import cfscrape


CHUNK_SIZE = 4 * 1024  # 4 KB


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


def clean_url(url: str) -> str:
    """Process a ReadComicOnline.to URL to make sure the page will be parsed correctly."""
    parsed_url = urlparse.urlparse(url)
    query_params = {
        **urlparse.parse_qs(parsed_url.query),
        'quality': ['hq'],
        'readType': ['1']
    }
    new_parsed_url = parsed_url._replace(query=urlparse.urlencode(query_params, doseq=True))
    return new_parsed_url.geturl()


def clean_title(title: str) -> str:
    return ' '.join(re.sub('[\\\/:*?"<>|\r\n]', '', title.split(' - ')[0].strip()).split())


def create_comic_book(name: str, input_dir: str):
    """Create a CBZ file from the files of an input directory."""
    with ZipFile(f'{name}.cbz', 'w') as zip_file:
        for filename in glob(os.path.join(input_dir, '*')):
            zip_file.write(filename, os.path.basename(filename))


def scrape_website(url) -> Tuple[str, List[str]]:
    session = cfscrape.create_scraper(delay=10)
    page = session.get(url)
    content = page.content.decode('utf-8')
    image_links = re.findall(r'lstImages.push\("(.*)"\);', content)
    title = clean_title(re.findall('<title>(.*)</title>', content, re.MULTILINE | re.DOTALL)[0])
    return title, image_links


def generate_comic_book(title, image_links):
    """Creates a CBZ on working directory with the images from *image_links*"""
    with tempfile.TemporaryDirectory() as tempdir:
        with closing(asyncio.get_event_loop()) as loop:
            loop.run_until_complete(download_files(image_links, tempdir))
        create_comic_book(title, tempdir)


def download_comic(url: str):
    """Download a comic from a ReadComicOnline.to url."""
    url = clean_url(url)
    title, image_links = scrape_website(url)
    generate_comic_book(title, image_links)
