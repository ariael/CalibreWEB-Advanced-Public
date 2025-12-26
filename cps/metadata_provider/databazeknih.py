# -*- coding: utf-8 -*-
import re
import requests
import random
from typing import List, Optional
from urllib.parse import quote
from multiprocessing.pool import ThreadPool
from lxml.html import fromstring, tostring
from cps import logger
from cps.services.Metadata import MetaRecord, MetaSourceInfo, Metadata

log = logger.create()

class Databazeknih(Metadata):
    __name__ = "Databazeknih.cz"
    __id__ = "databazeknih"

    BASE_URL = "https://www.databazeknih.cz"
    SEARCH_URL = "https://www.databazeknih.cz/vyhledavani/knihy?q={}"
    
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36'
    ]

    def _get_headers(self):
        return {'User-Agent': random.choice(self.USER_AGENTS)}

    def search(self, query: str, generic_cover: str = "", locale: str = "en") -> Optional[List[MetaRecord]]:
        if not self.active: return []
        try:
            url = self.SEARCH_URL.format(quote(query))
            resp = requests.get(url, headers=self._get_headers(), timeout=15)
            resp.raise_for_status()
            root = fromstring(resp.content)
            
            # Search results are usually in p.new or inside div wrappers
            results = root.xpath("//a[contains(@href, 'knihy/') and not(contains(@href, 'vyhledavani'))]")
            matches = []
            seen_urls = set()
            
            for node in results:
                book_rel_url = node.get("href")
                if not book_rel_url or "/knihy/" not in book_rel_url: continue
                if book_rel_url in seen_urls: continue
                seen_urls.add(book_rel_url)
                
                title = node.text_content().strip()
                if not title: continue
                
                book_url = self.BASE_URL + "/" + book_rel_url.lstrip("/")
                book_id = "dk_" + book_rel_url.split("-")[-1]
                
                # Try to find author (usually in span.pozn near the link)
                authors = []
                parent = node.getparent()
                if parent is not None:
                     author_node = parent.xpath(".//span[@class='pozn']")
                     if author_node:
                         auth_text = author_node[0].text_content().strip()
                         # Remove year (e.g. "2020, Autor")
                         authors = [a.strip() for a in auth_text.split(',') if not a.strip().isdigit()]
                
                match = MetaRecord(
                    id=book_id, title=title, authors=authors, url=book_url,
                    source=MetaSourceInfo(id=self.__id__, description=self.__name__, link=self.BASE_URL)
                )
                matches.append(match)
                if len(matches) >= 10: break

            if matches:
                with ThreadPool(processes=5) as pool:
                    final_matches = pool.starmap(self._parse_book_page, [(m, generic_cover) for m in matches])
                return [m for m in final_matches if m]
            return matches
        except Exception as e:
            log.warning(f"Databazeknih search failed: {e}")
            return None

    def _parse_book_page(self, match: MetaRecord, generic_cover: str) -> Optional[MetaRecord]:
        try:
            resp = requests.get(match.url, headers=self._get_headers(), timeout=15)
            root = fromstring(resp.content)
            
            # Title & Authors
            t_node = root.xpath("//h1[@itemprop='name']")
            if t_node: match.title = t_node[0].text_content().strip()
            
            a_nodes = root.xpath("//h2[@class='jmeno_autora']/a")
            if a_nodes: match.authors = [a.text_content().strip() for a in a_nodes]
            
            # Description
            desc_node = root.xpath("//p[@id='p_text']")
            if desc_node: match.description = tostring(desc_node[0], encoding='unicode')
            
            # Rating
            r_node = root.xpath("//div[@class='b_detail_rating']")
            if r_node:
                r_text = r_node[0].text_content().strip().replace('%', '')
                if r_text.isdigit(): match.rating = int(round(int(r_text) / 10.0))
            
            # Cover
            c_node = root.xpath("//img[@class='kniha_img']/@src")
            if c_node: match.cover = self.BASE_URL + c_node[0] if not c_node[0].startswith("http") else c_node[0]
            
            # Publisher & Date
            pub_node = root.xpath("//span[@itemprop='publisher']/a")
            if pub_node: match.publisher = pub_node[0].text_content().strip()
            
            date_node = root.xpath("//span[@itemprop='datePublished']")
            if date_node: match.publishedDate = date_node[0].text_content().strip()
            
            # ISBN
            isbn_node = root.xpath("//span[@itemprop='isbn']")
            if isbn_node: match.identifiers['isbn'] = isbn_node[0].text_content().strip()
            
            # Series
            series_node = root.xpath("//a[contains(@href, 'serie/')]")
            if series_node:
                s_text = series_node[0].text_content().strip()
                match.series = s_text
                # Try to extract index if format is "Series (Index)"
                idx_match = re.search(r'\((\d+)\.\)', s_text)
                if idx_match:
                    match.series_index = float(idx_match.group(1))
                    match.series = re.sub(r'\s*\(\d+\.\)$', '', s_text)
            
            # Tags (Genres)
            tag_nodes = root.xpath("//h5[@itemprop='genre']/a") or root.xpath("//a[contains(@href, 'zanry/')]")
            match.tags = list(set([t.text_content().strip() for t in tag_nodes if t.text_content().strip()]))

            return match
        except Exception as e:
            log.warning(f"Error parsing DK page {match.url}: {e}")
            return match
