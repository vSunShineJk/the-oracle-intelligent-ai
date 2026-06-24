from ddgs import DDGS


def web_search(query: str, max_results: int = 5) -> list[dict]:
    """Search the web using DuckDuckGo. Returns a list of results with title, url, and snippet."""
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=max_results, region="wt-wt"))
    return [{"title": r["title"], "url": r["href"], "snippet": r["body"]} for r in results]
