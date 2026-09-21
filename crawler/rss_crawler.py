import feedparser
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from crawler.base_crawler import BaseCrawler

MAX_AGE_HOURS = 72  # Drop articles older than 72 hours

def _parse_published(entry) -> datetime:
    """Parse published date from RSS entry, return UTC datetime."""
    for field in ["published_parsed", "updated_parsed"]:
        t = entry.get(field)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    raw = entry.get("published") or entry.get("updated", "")
    if raw:
        try:
            return parsedate_to_datetime(raw).astimezone(timezone.utc)
        except Exception:
            pass
    return datetime.now(timezone.utc)

class RSSCrawler(BaseCrawler):
    def __init__(self):
        super().__init__(delay=1)

    def crawl(self, feed_urls: list, max_age_hours: int = MAX_AGE_HOURS) -> list:
        articles = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        for url in feed_urls:
            try:
                feed = feedparser.parse(url)
                fresh = 0
                stale = 0
                for entry in feed.entries:
                    pub = _parse_published(entry)
                    if pub < cutoff:
                        stale += 1
                        continue
                    article = {
                        "title": entry.get("title", ""),
                        "summary": entry.get("summary", ""),
                        "url": entry.get("link", ""),
                        "published": pub.isoformat(),
                        "published_at": pub.isoformat(),
                        "source": url
                    }
                    articles.append(article)
                    fresh += 1
                print(f"[RSSCrawler] {url[:60]} → {fresh} fresh, {stale} stale dropped")
            except Exception as e:
                print(f"[RSSCrawler] Failed {url}: {e}")
        return articles
