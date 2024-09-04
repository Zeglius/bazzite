import re

from bs4 import BeautifulSoup, PageElement, Tag
from mkdocs import plugins
from mkdocs.utils import log as _l

NAME = "fix_img_urls"

broken_link_re = r"(?:\.\.?\/)+(https:/\b)"


def log_info(msg, /, *args, ljust=0, padding_char="\t", **kargs):
    _l.info(f"{NAME}: {padding_char * ljust}{msg}", *args, **kargs)


@plugins.event_priority(-50)
def on_page_content(html: str, **kargs):
    soup = BeautifulSoup(html, "html.parser")
    for el in soup.findAll("img"):
        if not isinstance(el, Tag):
            continue
        if not re.match(broken_link_re, el["src"], flags=re.M | re.I):
            continue
        log_info("Found broken link: ", el["src"])
        el["src"] = re.sub(broken_link_re, r"\1/", el["src"])
    return soup.prettify()
