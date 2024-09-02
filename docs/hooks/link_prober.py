from html.parser import HTMLParser

import requests
import urllib3.util
from mkdocs import plugins
from mkdocs.config.defaults import MkDocsConfig
from mkdocs.utils import log as _l

NAME = "link_prober"


def log_info(msg, /, *args, ljust=0, padding_char="\t", **kargs):
    _l.info(f"{NAME}: {padding_char * ljust}{msg}", *args, **kargs)


def log_debug(msg, /, *args, ljust=0, padding_char="\t", **kargs):
    _l.debug(f"{NAME}: {padding_char * ljust}{msg}", *args, **kargs)


def log_warning(msg, /, *args, ljust=0, padding_char="\t", **kargs):
    _l.warning(f"{NAME}: {padding_char * ljust}{msg}", *args, **kargs)


class LinkProberParser(HTMLParser):
    # NOTE: Add here http status codes that you might want to ignore
    IGNORE_STATUS_CODES = [405]

    def __init__(self, *, convert_charrefs: bool = True, site_url: str) -> None:
        super().__init__(convert_charrefs=convert_charrefs)
        self.site_url = site_url
        self._session = requests.Session()
        self._urls_to_probe: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        for href in [v for k, v in attrs if k == "href" and v]:
            url = urllib3.util.parse_url(href)
            # Check if is an external url
            if url.url.startswith(self.site_url) or url.scheme != "https":
                continue
            log_debug("Found an url: %s", url.url)
            self._urls_to_probe.add(url.url)

    def probe_urls(self):
        num_urls = len(self._urls_to_probe)
        count = 1
        for url, _ in map(self._probe_url, self._urls_to_probe):
            log_info(
                f"Probing [{count}/{num_urls}] {getattr(url, "url", url)}",
                ljust=1,
            )
            count += 1

    def _probe_url(self, url: str | urllib3.util.Url):
        req: requests.Response | None = None

        try:
            req = self._session.head(
                url if isinstance(url, str) else url.url,
                timeout=10,
                allow_redirects=True,
                stream=True,
            )
        except requests.exceptions.ReadTimeout:
            pass
        return url, req


link_prober: LinkProberParser


def on_config(config: MkDocsConfig):
    global link_prober
    link_prober = LinkProberParser(site_url=config.site_url)


@plugins.event_priority(-100)
def on_page_content(html: str, **kargs):
    link_prober.feed(html)


def on_post_build(*args, **kargs):
    log_info("Starting link probing...")
    link_prober.probe_urls()
