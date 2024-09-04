import hashlib
import os
import sys
from pathlib import Path

from bs4 import BeautifulSoup, Tag
import yaml
from mkdocs import plugins
from mkdocs.config.defaults import MkDocsConfig
from mkdocs.structure.files import Files
from mkdocs.structure.pages import Page

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import re
from copy import copy

from fetch_discourse_md import fetch as fetch_md_discourse

CMDRUN_PATTERN = r"<!--\s?cmdrun\s+fetch_discourse_md\.py\s+\"(.*)\"\s*-->"
PLUGIN_NAME = os.path.basename(__file__).rstrip(".py")

plugin_cache_dir: str
url_mappings: dict = {}
"""Dict with mappings for discourse urls to be replaced with mkdocs ones"""


def log_info(*args):
    return print(f"{PLUGIN_NAME}:", *args)


def _cache_filename_generator(text: str) -> str:
    """Generate a sha265 encoded cache file path of a piece of text inside the plugin cache dir"""
    cache_file = os.path.join(
        plugin_cache_dir, hashlib.sha256(text.encode()).hexdigest()
    )
    return cache_file


def _fetch_callback(url: str):
    cache_file = _cache_filename_generator(url)
    if os.path.exists(cache_file):
        return Path(cache_file).read_text().strip()

    elif content := fetch_md_discourse(url):
        with open(cache_file, "w+t") as c_file:
            c_file.write(content)
        return content
    else:
        return ""


def _cmdrun_sub_handler(match: re.Match) -> str:
    print(match.group(1))
    url = match.group(1)
    result = _fetch_callback(url)
    return result or ""


def on_config(config: MkDocsConfig):
    """Initialize configuration"""
    global plugin_cache_dir, url_mappings
    mkdocs_config_dir = os.path.dirname(config.config_file_path)
    plugin_cache_dir = os.path.join(mkdocs_config_dir, ".cache", PLUGIN_NAME)
    try:
        os.makedirs(plugin_cache_dir, exist_ok=True)
    except FileExistsError:
        pass

    try:
        url_overrides_file = os.path.join(mkdocs_config_dir, "url_overrides.yml")
        with open(url_overrides_file) as f:
            url_mappings = yaml.load(f.read(), Loader=yaml.SafeLoader)
    except FileNotFoundError:
        log_info(
            f"'{os.path.relpath(url_overrides_file)}' doesnt exist, using default mapping '{url_mappings}'"
        )


@plugins.event_priority(100)
def on_page_markdown(markdown: str, **kargs):
    """Replace `<!-- cmdrun` placeholders with discourse post contents"""
    markdown_orig = markdown
    result = copy(markdown_orig)

    try:
        result = re.sub(CMDRUN_PATTERN, _cmdrun_sub_handler, markdown_orig)
    except Exception as err:
        print("ERROR", err)

    return result


@plugins.event_priority(100)
def on_page_content(
    html: str,
    page: Page,
    config: MkDocsConfig,
    files: Files,
    **kargs,
):
    """Replace discourse urls"""
    soup = BeautifulSoup(html)
    for el in soup.find_all("a"):
        if not isinstance(el, Tag):
            continue
        # Replace the href if is in url_mappings, else dont replace it
        if el["href"] in url_mappings.keys():
            el["href"] = url_mappings[el["href"]]

    return soup.prettify()
