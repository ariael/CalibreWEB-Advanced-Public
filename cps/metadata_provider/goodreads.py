# -*- coding: utf-8 -*-

#  This file is part of the Calibre-Web (https://github.com/janeczku/calibre-web)
#    Copyright (C) 2024 OzzieIsaacs
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program. If not, see <http://www.gnu.org/licenses/>.

import re
from typing import List, Optional
from urllib.parse import quote
from multiprocessing.pool import ThreadPool

import requests
from lxml.html import fromstring, tostring

from cps import logger
from cps.services.Metadata import MetaRecord, MetaSourceInfo, Metadata

log = logger.create()


class Goodreads_Provider(Metadata):
    __name__ = "Goodreads"
    __id__ = "goodreads_scraper" # Avoid conflict with goodreads_api if any

    BASE_URL = "https://www.goodreads.com"
    SEARCH_URL = "https://www.goodreads.com/search?q={}"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    def search(
        self, query: str, generic_cover: str = "", locale: str = "en"
    ) -> Optional[List[MetaRecord]]:
        if self.active:
            try:
                query_encoded = quote(query.replace(' ', '+'))
                url = self.SEARCH_URL.format(query_encoded)

                result = requests.get(url, headers=self.headers)
                result.raise_for_status()
            except Exception as e:
                log.warning(f"Goodreads search error: {e}")
                return None

            root = fromstring(result.content)
            
            # Goodreads search results are usually in a table with itemtype schema.org/Book
            # //tr[@itemtype="http://schema.org/Book"]
            results = root.xpath('//tr[@itemtype="http://schema.org/Book"]')
            
            matches = []
            for node in results[:10]: # Limit to top 10 to fetch details
                try:
                    # Title & URL
                    link_node = node.xpath('.//a[@class="bookTitle"]')
                    if not link_node:
                        continue
                    link_node = link_node[0]
                    
                    full_title = link_node.text_content().strip()
                    book_rel_url = link_node.get("href")
                    
                    if not book_rel_url.startswith("http"):
                        book_url = self.BASE_URL + "/" + book_rel_url.lstrip("/")
                    else:
                        book_url = book_rel_url

                    # Author
                    author_node = node.xpath('.//a[@class="authorName"]')
                    authors = []
                    if author_node:
                        # There can be multiple authors
                        authors = [a.text_content().strip() for a in author_node]

                    # Create basic match
                    # ID extraction: Goodreads URL usually /book/show/12345.Title
                    book_id = ""
                    id_match = re.search(r'/show/(\d+)', book_url)
                    if id_match:
                        book_id = id_match.group(1)
                    
                    match = MetaRecord(
                        id=book_id,
                        title=full_title,
                        authors=authors,
                        url=book_url,
                        source=MetaSourceInfo(
                            id=self.__id__,
                            description=self.__name__,
                            link=self.BASE_URL,
                        ),
                    )
                    matches.append(match)
                except Exception as e:
                    log.warning(f"Error parsing Goodreads search result: {e}")
                    continue

            # Fetch details in parallel
            if matches:
                # Use fewer threads to avoid rate limiting
                with ThreadPool(processes=4) as pool:
                    final_matches = pool.starmap(
                        self._parse_book_page,
                        [(match, generic_cover) for match in matches],
                    )
                return [m for m in final_matches if m]
            
            return matches
        return []

    def _parse_book_page(self, match: MetaRecord, generic_cover: str) -> Optional[MetaRecord]:
        try:
            response = requests.get(match.url, headers=self.headers)
            response.raise_for_status()
        except Exception as e:
            log.warning(f"Goodreads detail error for {match.url}: {e}")
            return match

        try:
            root = fromstring(response.content)
            
            # Goodreads has two layouts: Old (Rails) and New (React)
            # We attempt to detect the new layout by looking for data-testid
            
            is_new_layout = bool(root.xpath('//*[@data-testid="bookTitle"]'))

            if is_new_layout:
                self._parse_react_layout(root, match)
            else:
                self._parse_classic_layout(root, match)
            
            return match

        except Exception as parse_e:
            log.warning(f"Goodreads parsing error: {parse_e}")
            return match

    def _parse_react_layout(self, root, match):
        # Title
        title_node = root.xpath('//*[@data-testid="bookTitle"]')
        if title_node:
            match.title = title_node[0].text_content().strip()
        
        # Author using ContributorLink__name (can be span or a)
        # .//span[@class="ContributorLink__name"] or .//a...
        # Using contains because sometimes they add extra classes
        author_nodes = root.xpath('//*[contains(@class, "ContributorLink__name")]')
        if author_nodes:
            # unique authors
            match.authors = list(dict.fromkeys([a.text_content().strip() for a in author_nodes]))
        
        # Rating
        # .RatingStatistics__rating
        rating_node = root.xpath('//*[contains(@class, "RatingStatistics__rating")]')
        if rating_node:
            try:
                val = float(rating_node[0].text_content().strip())
                # Calibre uses 1-10 (roughly stars * 2)
                match.rating = int(round(val * 2))
            except:
                pass
        
        # Description
        desc_node = root.xpath('//*[@data-testid="description"]')
        if desc_node:
            # We want the text inside, usually inside a span with class "Formatted"
            # match.description = tostring(desc_node[0], encoding='unicode')
            # But better to just take text_content if tostring fails or use inner HTML
            # Just taking the inner HTML of the node
            # The node itself is a div, content might be in span
            spans = desc_node[0].xpath('.//span[contains(@class, "Formatted")]')
            if spans:
                match.description = tostring(spans[-1], encoding='unicode') # usually last span checks for "more"
            else:
                match.description = tostring(desc_node[0], encoding='unicode')

        # Cover
        # img.ResponsiveImage inside .BookCover__image
        # But generic ResponsiveImage might catch others.
        # usually //div[@class="BookCover__image"]//img
        cover_node = root.xpath('//div[contains(@class, "BookCover__image")]//img')
        if cover_node:
            src = cover_node[0].get("src")
            if src:
                match.cover = src
        
        # Publisher & Pub Date
        # [data-testid="publicationInfo"] -> "First published June 8, 1949"
        pub_info = root.xpath('//*[@data-testid="publicationInfo"]')
        if pub_info:
            text = pub_info[0].text_content().strip()
            # Try to extract date
            match.publishedDate = text.replace("First published", "").replace("Published", "").strip()
        
        # Publisher specifically is harder in new layout, often hidden in details
        # Check dl keys
        # //div[contains(@class, "DescListItem")]
        details = root.xpath('//div[contains(@class, "DescListItem")]')
        for d in details:
            dt = d.xpath('.//dt')
            dd = d.xpath('.//dd')
            if dt and dd:
                label = dt[0].text_content().lower()
                val = dd[0].text_content().strip()
                if 'publisher' in label:
                    match.publisher = val
                elif 'isbn' in label:
                     # 1984 (ISBN13: ...)
                     # extract pure digits or isbn
                     match.identifiers['isbn'] = val.split(' ')[0]

    def _parse_classic_layout(self, root, match):
        # Fallback for classic layout
        title_node = root.xpath('//h1[@id="bookTitle"]')
        if title_node:
            match.title = title_node[0].text_content().strip()
        
        # Authors
        author_nodes = root.xpath('//a[@class="authorName"]')
        if author_nodes:
             match.authors = list(dict.fromkeys([a.text_content().strip() for a in author_nodes]))
        
        # Rating
        rating_node = root.xpath('//span[@itemprop="ratingValue"]')
        if rating_node:
            try:
                val = float(rating_node[0].text_content().strip())
                match.rating = int(round(val * 2))
            except:
                pass
        
        # Description
        desc_node = root.xpath('//div[@id="description"]')
        if desc_node:
            spans = desc_node[0].xpath('.//span[contains(@style, "display:none")]')
            if spans:
                 match.description = tostring(spans[0], encoding='unicode')
            else:
                 visible_spans = desc_node[0].xpath('.//span')
                 if visible_spans:
                     match.description = tostring(visible_spans[0], encoding='unicode')
        
        # Cover
        cover_node = root.xpath('//img[@id="coverImage"]')
        if cover_node:
            match.cover = cover_node[0].get("src")

        # Publisher / Date
        # details are in #bookDataBox
        publisher_node = root.xpath('//div[@id="bookDataBox"]//div[contains(text(), "Publisher")]/following-sibling::div')
        if publisher_node:
             match.publisher = publisher_node[0].text_content().strip()
             
        # ISBN
        isbn_node = root.xpath('//div[@id="bookDataBox"]//div[contains(text(), "ISBN")]/following-sibling::div')
        if isbn_node:
             match.identifiers['isbn'] = isbn_node[0].text_content().strip()

