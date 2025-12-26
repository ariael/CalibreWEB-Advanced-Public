# -*- coding: utf-8 -*-
import requests
import random
import re
from typing import List, Optional
from urllib.parse import quote
from lxml.html import fromstring, tostring
from multiprocessing.pool import ThreadPool
from cps import logger
from cps.services.Metadata import MetaRecord, MetaSourceInfo, Metadata

log = logger.create()

class Amazon(Metadata):
    __name__ = "Amazon"
    __id__ = "amazon"

    BASE_URLS = [
        "https://www.amazon.com",
        "https://www.amazon.co.uk",
        "https://www.amazon.de"
    ]
    
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36'
    ]

    def _get_headers(self):
        return {
            'User-Agent': random.choice(self.USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

    def search(self, query: str, generic_cover: str = "", locale: str = "en") -> Optional[List[MetaRecord]]:
        if not self.active: return []
        
        # Decide which Amazon domain to use based on locale or preference
        base_url = self.BASE_URLS[0] # Default to .com
        if locale == 'de': base_url = "https://www.amazon.de"
        elif locale == 'en_GB': base_url = "https://www.amazon.co.uk"

        try:
            search_url = f"{base_url}/s?k={quote(query)}&i=stripbooks"
            resp = requests.get(search_url, headers=self._get_headers(), timeout=15)
            resp.raise_for_status()
            root = fromstring(resp.content)
            
            # Find search results
            results = root.xpath("//div[@data-component-type='s-search-result']")
            matches = []
            
            for node in results[:5]: # Limit to top 5 for deep scan
                try:
                    title_node = node.xpath(".//h2//a")[0]
                    title = title_node.text_content().strip()
                    rel_url = title_node.get("href")
                    if not rel_url: continue
                    
                    full_url = base_url + rel_url if not rel_url.startswith("http") else rel_url
                    # Clean URL (strip tracking params)
                    full_url = full_url.split('/ref=')[0]
                    
                    # ASIN/ID
                    asin = node.get("data-asin")
                    
                    match = MetaRecord(
                        id=asin,
                        title=title,
                        authors=[],
                        url=full_url,
                        source=MetaSourceInfo(id=self.__id__, description=self.__name__, link=base_url)
                    )
                    matches.append(match)
                except Exception: continue

            if matches:
                 with ThreadPool(processes=4) as pool:
                     final = pool.starmap(self._parse_details, [(m, base_url) for m in matches])
                 return [m for m in final if m]
            return []
        except Exception as e:
            log.warning(f"Amazon search failed: {e}")
            return None

    def _parse_details(self, match: MetaRecord, base_url: str) -> Optional[MetaRecord]:
        try:
            resp = requests.get(match.url, headers=self._get_headers(), timeout=15)
            root = fromstring(resp.content)
            
            # Title
            t_node = root.xpath("//span[@id='productTitle']")
            if t_node: match.title = t_node[0].text_content().strip()
            
            # Authors
            a_nodes = root.xpath("//span[@class='author notincalc']//a") or \
                      root.xpath("//div[@id='bylineInfo']//a")
            if a_nodes:
                 match.authors = [a.text_content().strip() for a in a_nodes if "search" not in a.get("href", "")]
            
            # Description
            d_node = root.xpath("//div[@data-feature-name='bookDescription']//div[contains(@class, 'a-expander-content')]")
            if d_node:
                match.description = tostring(d_node[0], encoding='unicode')
            
            # Rating
            r_node = root.xpath("//span[@id='acrPopover']/@title")
            if r_node:
                val = re.search(r'(\d[\.,]\d)', r_node[0])
                if val:
                    match.rating = int(round(float(val.group(1).replace(',', '.')) * 2))
            
            # Cover
            c_node = root.xpath("//img[@id='imgBlkFront' or @id='ebooksImgBlkFront']/@src")
            if c_node: match.cover = c_node[0]
            
            # Details: ISBN, Publisher, series
            details_text = tostring(root.xpath("//div[@id='detailBullets_feature_div']")[0], encoding='unicode') if root.xpath("//div[@id='detailBullets_feature_div']") else ""
            
            # ISBN-13
            isbn_match = re.search(r'ISBN-13.*?(\d{3}-\d+)', details_text, re.IGNORECASE | re.DOTALL)
            if isbn_match: match.identifiers['isbn'] = isbn_match.group(1).replace('-', '')
            
            # Publisher
            pub_match = re.search(r'Publisher.*?</span>.*?<span>(.*?)\(', details_text, re.IGNORECASE | re.DOTALL)
            if pub_match: match.publisher = pub_match.group(1).strip()
            
            # Series
            series_node = root.xpath("//div[@id='seriesBulletWidget_feature_div']//a")
            if series_node:
                match.series = series_node[0].text_content().strip()
                # Try to extract index
                idx_match = re.search(r'Book (\d+)', series_node[0].text_content())
                if idx_match: match.series_index = float(idx_match.group(1))

            return match
        except Exception as e:
            log.debug(f"Amazon detail parse failed for {match.url}: {e}")
            return match
