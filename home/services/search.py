from ..search_registry import collect_search_results


def run_global_search(query: str, active_cats: set, user, limit: int = 10) -> list:
    """Return a list of search result dicts across the selected categories."""
    return collect_search_results(query, active_cats, user, limit)
