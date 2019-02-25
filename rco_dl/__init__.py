"""ReadComicOnline.to Downloader"""
import sys

from .rco_dl import download_comic

__version__ = '1.3'

def main():
    download_comic(sys.argv[1])
