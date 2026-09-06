"""Registry for per-application global search providers.

Each application that contributes search results:
1. implements a `search(query, active_cats, user, limit)` function in
   `<app>/search.py`;
2. registers it in `<app>/apps.py::ready()` with the categories it handles.

`home` no longer imports models from other apps to build search results.
"""

from dataclasses import dataclass
from typing import Callable

SearchProvider = Callable[[str, set[str], object, int], list[dict]]


@dataclass
class SearchEntry:
    categories: frozenset[str]
    search: SearchProvider


_providers: list[SearchEntry] = []


def register_search_provider(*categories: str, search: SearchProvider) -> None:
    _providers.append(SearchEntry(categories=frozenset(categories), search=search))


def collect_search_results(query: str, active_cats: set[str], user, limit: int = 10) -> list[dict]:
    """Return combined search results from all providers matching active categories."""
    if not query:
        return []

    results = []
    for entry in _providers:
        if entry.categories & active_cats:
            results.extend(entry.search(query, active_cats, user, limit))
    return results
