#!/usr/bin/python

__doc__ = """ Utility to extract pages from Discourse posts in a Markdown format

@author: Zeglius

Quick Glossary:
    - HTMLPage: an HTML page contents
    - Markdown: a Markdown page contents

How does this script work:
    1.  Pass Discourse docs topic URL as argument
        ```sh
        ./fetch_discourse_md.py "https://universal-blue.discourse.group/docs?topic=1146"
        ```

    2.  Create an UrlBatch for each URL passed.
        An UrlBatch is a named tuple which contents are:
            - An URL pointing to the raw markdown of the topic (ex.: https://universal-blue.discourse.group/raw/1146)
            - An URL pointing to the json format of the topic (ex.: https://universal-blue.discourse.group/t/1146.json)

    We have a problem. We could simply use the raw markdown, but in that format, images URLs point to a route that Discourse
    use internally to fetch the images (ex:. upload://AliS5ytuj3Rro4xsxfHMnPiJMsR.jpeg).

    The solution lies in the json format of the topic. Specifically its field '.post_stream.posts[].cooked'.
    That field contains the already rendered html page, including the URLs pointing to the images in the CDN.

    Problem is, how do we match the images images in the markdown (ex.: upload://AliS5ytuj3Rro4xsxfHMnPiJMsR.jpeg) with the ones
    from the json (ex.: https://canada1.discourse-cdn.com/free1/uploads/univeral_blue/original/2X/f/feb6c68dc90b80d9432b6ce74a38f639b05202d5.jpeg)?
    
    This is an extract of the img element:

    ```html
    <img src="https://canada1.discourse-cdn.com/free1/uploads/univeral_blue/original/2X/f/feb6c68dc90b80d9432b6ce74a38f639b05202d5.jpeg" 
    alt="Desktop" 
    data-base62-sha1="AliS5ytuj3Rro4xsxfHMnPiJMsR" 
    width="690" height="448" data-dominant-color="4D5A5D">
    ```

    Bingo! `data-base62-sha1` contents match with that of the image URL in the markdown (ex.: upload://AliS5ytuj3Rro4xsxfHMnPiJMsR.jpeg).

    3.  Obtain the HTML page contents using the json url stored in the UrlBatch
        ```python
        @classmethod    
        def get_page_from_json(cls, batch: UrlBatch) -> HTMLPage:
            json_content = requests.get(batch.json_url).json()
            return json_content["post_stream"]["posts"][0]["cooked"]
        ```

    4.  From the HTML page, find the `<img>` tags with the next regex expression:
        ```regex
        <img src=\"(?P<image_cdn_url>https://(?:[a-zA-Z0-9./_-]+)).*data-base62-sha1=\"(?P<sha1>[a-zA-Z0-9]+)\".*\">
        ```
        Using this regex expression we obtain:
            - URL used by the CDN to store the image (group 'image_cdn_url')
            - SHA1 used by the markdown (ex.: upload://<SHA1>.jpeg) (group 'sha1')

    5.  Create a `img_url_assocs: list[tuple[str,str]]`, `dict` following this schema: `{"<SHA1>": "<image_cdn_url>"}`
        ```python
        @classmethod
        def get_images_url_assocs_from_page(cls, page: HTMLPage) -> list[tuple[str, str]]:
            result: list[dict[str, str]] = []
            for match in re.finditer(DiscourseProcessor.Patterns.imgs_urls, page):
                (sha1, image_cdn_url) = match.group("sha1", "image_cdn_url")
                result.append({sha1: image_cdn_url})
            return result
        ```

    Once we have associated each SHA1 with an image_cdn_url, its time to fetch the Markdown
    
    6.  Obtain markdown
        ```python
        @classmethod
        def get_markdown_from_raw(cls, batch: UrlBatch) -> Markdown:
            return requests.get(batch.raw_url).text
        ```

    7.  For each key in the `img_url_assocs` list, search with regex the _hashed urls_ (ex.: upload://AliS5ytuj3Rro4xsxfHMnPiJMsR.jpeg)
        and replace them with the image_cdn_url
        ```python
        for assoc in img_url_assocs:
            # TODO: Add example here
        ```
"""


from collections import namedtuple
from argparse import ArgumentParser
import os
import re
from sys import stdout

import requests


_BASE_URL = os.getenv("BASE_URL", "https://universal-blue.discourse.group").rstrip("/")


UrlBatch = namedtuple("UrlBatch", ["raw_url", "json_url"])


type HTMLPage = str
type Markdown = str
type ImageUrlAssocs = list[tuple[str, str]]


class DiscourseProcessor:

    class Patterns:
        post_sep_markdown = re.compile(r"-------------------------")
        imgs_urls = re.compile(
            r"<img\ssrc=\"(?P<image_cdn_url>https://(?:[a-zA-Z0-9./_-]+)).*data-base62-sha1=\"(?P<sha1>[a-zA-Z0-9]+)\".*\">"
        )
        hashed_images_urls = re.compile(r"upload://[a-zA-Z0-9]{27}\.(?:jpe?g|png|svg)")

    @staticmethod
    def is_valid_doc_topic_url(url: str) -> bool:
        """Check if the passed discourse topic url is valid doc

        Args:
            url (str)

        Returns:
            bool
        """

        return (
            # re.match(r"https\:\/\/universal-blue\.discourse\.group/docs\?topic=\d+", url)
            re.match(
                re.escape(_BASE_URL) + r"/docs\?topic=\d+",
                url,
            )
            is not None
        )

    @classmethod
    def transform_to_url_batch(cls, url: str) -> UrlBatch | None:
        """Input a discourse url topic and return a batch of urls such as `/raw/{id}` and `/t/{id}.json`

        Args:
            url (str)
        """
        res = None

        if not cls.is_valid_doc_topic_url(url):
            raise TypeError("Url is not valid")

        # Get topic id
        id = re.search(re.escape(_BASE_URL) + r"/docs\?topic=(\d+)", url)
        if id is None:
            raise Exception("id was not found")
        id = int(id.group(1))

        res = UrlBatch(
            json_url=f"https://universal-blue.discourse.group/t/{id}.json",
            raw_url=f"https://universal-blue.discourse.group/raw/{id}",
        )

        return res

    @classmethod
    def get_page_from_json(cls, batch: UrlBatch) -> HTMLPage:
        """Get webpage contents from an url link

        This includes images urls from discourse cdn

        Args:
            batch (UrlBatch)
        """
        json_content = requests.get(batch.json_url).json()

        # json_content = json.loads(json_content)
        return json_content["post_stream"]["posts"][0]["cooked"]

    @classmethod
    def get_markdown_from_raw(cls, batch: UrlBatch) -> Markdown:
        """Get markdown from page

        This is recommended for extracting text transcriptions

        Args:
            batch (UrlBatch): _description_

        Returns:
            str:
        """

        return requests.get(batch.raw_url).text

    @classmethod
    def get_images_url_assocs_from_page(cls, page: HTMLPage) -> ImageUrlAssocs:
        result: list[tuple] = []
        for match in re.finditer(DiscourseProcessor.Patterns.imgs_urls, page):
            (sha1, image_cdn_url) = match.group("sha1", "image_cdn_url")
            result.append((sha1, image_cdn_url))
        return result

    @classmethod
    def replace_images_urls_in_markdown(
        cls, page: Markdown, assocs: ImageUrlAssocs
    ) -> Markdown:
        result = page
        for assoc in assocs:
            result = result.replace(
                "upload://" + assoc[0],
                os.path.splitext(assoc[1])[0],
            )
        return result


def main():
    argparser = ArgumentParser()
    argparser.add_argument(
        "url",
        type=str,
        nargs=1,  # Change this to `+` if you wish to process multiple urls
        help="discourse urls to be processed",
    )
    args = argparser.parse_args()

    urls = args.url

    urls_batches_list: list[UrlBatch] = []

    for url in urls:
        batch = DiscourseProcessor.transform_to_url_batch(url)
        if batch is None:
            continue
        urls_batches_list.append(batch)

    for batch in urls_batches_list:
        image_urls_assocs = DiscourseProcessor.get_images_url_assocs_from_page(
            DiscourseProcessor.get_page_from_json(batch)
        )
        result = DiscourseProcessor.replace_images_urls_in_markdown(
            page=DiscourseProcessor.get_markdown_from_raw(batch),
            assocs=image_urls_assocs,
        )

        # Remove comments

        result = DiscourseProcessor.Patterns.post_sep_markdown.split(result, 1)[0].rstrip()

        print(result, file=stdout)


if __name__ == "__main__":
    main()