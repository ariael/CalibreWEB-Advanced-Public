# -*- coding: utf-8 -*-

from typing import List, Optional, Dict
import requests
from cps import logger, config
from cps.services.Metadata import MetaRecord, MetaSourceInfo, Metadata

log = logger.create()

class Hardcover(Metadata):
    __name__ = "Hardcover.app"
    __id__ = "hardcover"
    DESCRIPTION = "Hardcover.app Book Metadata"
    META_URL = "https://hardcover.app/"
    API_URL = "https://api.hardcover.app/v1/graphql"

    def search(
        self, query: str, generic_cover: str = "", locale: str = "en"
    ) -> Optional[List[MetaRecord]]:
        val = list()
        if not self.active or not config.config_hardcover_api_key:
            return val

        # GraphQL query for searching books
        # We use a direct query for more structured control
        graphql_query = """
        query GetBooksByTitle($title: String!) {
          books(where: {title: {_ilike: $title}}, limit: 10) {
            id
            title
            description
            release_date
            rating
            ratings_count
            image {
              url
            }
            contributions {
              author {
                name
              }
            }
            book_tags {
              tag {
                name
              }
            }
          }
        }
        """
        # Add wildcards for ilike
        variables = {'title': f"%{query}%"}
        headers = {
            'Authorization': config.config_hardcover_api_key,
            'Content-Type': 'application/json'
        }

        try:
            response = requests.post(self.API_URL, json={'query': graphql_query, 'variables': variables}, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            log.warning("Hardcover search failed: %s", e)
            return val

        if 'errors' in data:
            log.warning("Hardcover API errors: %s", data['errors'])
            return val

        for item in data.get('data', {}).get('books', []):
            val.append(self._parse_item(item, generic_cover))
        
        return val

    def _parse_item(self, item: Dict, generic_cover: str) -> MetaRecord:
        authors = []
        for contrib in item.get('contributions', []):
            author_name = contrib.get('author', {}).get('name')
            if author_name and author_name not in authors:
                authors.append(author_name)
        
        if not authors:
            authors = ["Unknown"]

        match = MetaRecord(
            id=item["id"],
            title=item["title"],
            authors=authors,
            url=f"https://hardcover.app/books/{item['id']}", # Slug would be better but ID works
            source=MetaSourceInfo(
                id=self.__id__,
                description=self.DESCRIPTION,
                link=self.META_URL,
            ),
        )

        match.description = item.get("description", "")
        if match.description:
            import re
            match.description = re.sub('<[^<]+?>', '', match.description)

        match.cover = item.get("image", {}).get("url") or generic_cover
        
        # Rating: Hardcover is 0-5, Calibre is 0-10
        if item.get("rating"):
            match.rating = int(item["rating"] * 2)
        
        # Date: release_date is usually YYYY-MM-DD
        if item.get("release_date"):
            match.publishedDate = item["release_date"]

        # Tags
        match.tags = [t['tag']['name'] for t in item.get('book_tags', []) if t.get('tag', {}).get('name')]
        
        # Identifiers
        match.identifiers = {"hardcover": str(item["id"])}
        
        return match
