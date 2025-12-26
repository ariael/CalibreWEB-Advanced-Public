# -*- coding: utf-8 -*-

from typing import List, Optional
import requests
from cps import logger
from cps.services.Metadata import MetaRecord, MetaSourceInfo, Metadata

log = logger.create()

class AniList(Metadata):
    __name__ = "AniList (Manga)"
    __id__ = "anilist"
    DESCRIPTION = "AniList Manga Metadata"
    META_URL = "https://anilist.co/"
    API_URL = "https://graphql.anilist.co"

    def search(
        self, query: str, generic_cover: str = "", locale: str = "en"
    ) -> Optional[List[MetaRecord]]:
        val = list()
        if not self.active:
            return val

        graphql_query = """
        query ($search: String) {
          Page(page: 1, perPage: 10) {
            media(search: $search, type: MANGA) {
              id
              title {
                romaji
                english
                native
              }
              coverImage {
                extraLarge
              }
              description(asHtml: false)
              averageScore
              genres
              staff {
                edges {
                  node {
                    name {
                      full
                    }
                  }
                  role
                }
              }
              startDate {
                year
                month
                day
              }
              idMal
              externalLinks {
                url
                site
              }
            }
          }
        }
        """
        variables = {'search': query}

        try:
            response = requests.post(self.API_URL, json={'query': graphql_query, 'variables': variables}, timeout=10)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            log.warning("AniList search failed: %s", e)
            return val

        for item in data.get('data', {}).get('Page', {}).get('media', []):
            val.append(self._parse_item(item, generic_cover))
        
        return val

    def _parse_item(self, item, generic_cover) -> MetaRecord:
        # Title selection
        title = item['title'].get('english') or item['title'].get('romaji') or item['title'].get('native')
        
        # Authors (Staff with role like "Story" or "Art")
        authors = []
        for edge in item.get('staff', {}).get('edges', []):
            role = edge.get('role', '').lower()
            if 'story' in role or 'art' in role or 'author' in role or 'illustrator' in role:
                name = edge.get('node', {}).get('name', {}).get('full')
                if name and name not in authors:
                    authors.append(name)
        
        if not authors:
            authors = ["Unknown"]

        match = MetaRecord(
            id=item["id"],
            title=title,
            authors=authors,
            url=f"https://anilist.co/manga/{item['id']}",
            source=MetaSourceInfo(
                id=self.__id__,
                description=self.DESCRIPTION,
                link=self.META_URL,
            ),
        )

        match.description = item.get("description", "")
        # Remove HTML tags from description if any (API handles asHtml: false but sometimes it leaks or has weird tags)
        if match.description:
            import re
            match.description = re.sub('<[^<]+?>', '', match.description)

        match.cover = item.get("coverImage", {}).get("extraLarge") or generic_cover
        
        # Rating: AniList is 0-100, Calibre is 0-10
        if item.get("averageScore"):
            match.rating = int(item["averageScore"] / 10)
        
        # Date
        sd = item.get("startDate", {})
        if sd.get("year"):
            match.publishedDate = f"{sd['year']}-{sd.get('month', 1):02d}-{sd.get('day', 1):02d}"

        match.tags = item.get("genres", [])
        
        # Identifiers
        match.identifiers = {"anilist": str(item["id"])}
        if item.get("idMal"):
            match.identifiers["mal"] = str(item["idMal"])
        
        return match
