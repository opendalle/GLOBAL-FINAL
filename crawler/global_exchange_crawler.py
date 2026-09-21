"""
Global Exchange Crawler — Nexus Asia CRE Intel
================================================
Crawls free public APIs and RSS feeds from global stock exchanges
for CRE-relevant filings and announcements.

Exchanges covered (all FREE, no API key needed):
  - SEC EDGAR  (USA) — 8-K, 10-K full-text search
  - LSE RNS    (UK)  — via Google News RSS
  - SGX        (SG)  — via Google News RSS
  - HKEX       (HK)  — via Google News RSS
  - ASX        (AU)  — via Google News RSS
  - TSX        (CA)  — via Google News RSS
  - Bursa      (MY)  — via Google News RSS
"""

import re
import time
from datetime import datetime, timedelta
from crawler.base_crawler import BaseCrawler

REQUEST_TIMEOUT = (10, 15)

CRE_KEYWORDS = [
    "office space", "square feet", "sqft", "sq ft", "office lease", "lease agreement",
    "new headquarters", "new hq", "office campus", "office premises", "new facility",
    "data center", "data centre", "warehouse", "logistics facility", "industrial space",
    "commercial real estate", "property lease", "leasehold", "tenancy agreement",
    "office expansion", "new office", "relocat", "commercial property",
]

NOISE_KEYWORDS = [
    "quarterly results", "dividend", "esop", "agm", "egm", "record date",
    "book closure", "auditor", "director appointment", "shareholding pattern",
    "credit rating", "analyst meet", "investor meet", "compliance", "penalty",
]

EXCHANGE_GNEWS_FEEDS = [
    # USA — SEC-related
    {
        "url": "https://news.google.com/rss/search?q=SEC+8-K+filing+office+lease+\"square+feet\"+2025&hl=en&gl=US&ceid=US:en",
        "exchange": "SEC_EDGAR", "country": "USA", "region": "USA",
    },
    {
        "url": "https://news.google.com/rss/search?q=company+\"new+headquarters\"+\"square+feet\"+lease+USA&hl=en&gl=US&ceid=US:en",
        "exchange": "SEC_EDGAR", "country": "USA", "region": "USA",
    },
    # UK — LSE RNS
    {
        "url": "https://news.google.com/rss/search?q=LSE+RNS+company+office+property+lease+announcement+UK&hl=en&gl=GB&ceid=GB:en",
        "exchange": "LSE_RNS", "country": "UK", "region": "UK",
    },
    {
        "url": "https://news.google.com/rss/search?q=UK+listed+company+office+relocation+headquarters+2025&hl=en&gl=GB&ceid=GB:en",
        "exchange": "LSE_RNS", "country": "UK", "region": "UK",
    },
    # Singapore — SGX
    {
        "url": "https://news.google.com/rss/search?q=SGX+announcement+office+property+Singapore+listed+company+2025&hl=en&gl=SG&ceid=SG:en",
        "exchange": "SGX", "country": "Singapore", "region": "Singapore",
    },
    {
        "url": "https://news.google.com/rss/search?q=Singapore+listed+company+new+office+headquarters+expansion+2025&hl=en&gl=SG&ceid=SG:en",
        "exchange": "SGX", "country": "Singapore", "region": "Singapore",
    },
    # Hong Kong — HKEX
    {
        "url": "https://news.google.com/rss/search?q=HKEX+listed+company+office+property+announcement+Hong+Kong+2025&hl=en&gl=HK&ceid=HK:en",
        "exchange": "HKEX", "country": "Hong Kong", "region": "China_HK",
    },
    # Australia — ASX
    {
        "url": "https://news.google.com/rss/search?q=ASX+listed+company+office+lease+property+announcement+2025&hl=en&gl=AU&ceid=AU:en",
        "exchange": "ASX", "country": "Australia", "region": "Australia",
    },
    # Canada — TSX
    {
        "url": "https://news.google.com/rss/search?q=TSX+listed+company+office+headquarters+lease+Canada+2025&hl=en&gl=CA&ceid=CA:en",
        "exchange": "TSX", "country": "Canada", "region": "Canada",
    },
    # Malaysia — Bursa
    {
        "url": "https://news.google.com/rss/search?q=Bursa+Malaysia+company+office+property+announcement+2025&hl=en&gl=MY&ceid=MY:en",
        "exchange": "BURSA", "country": "Malaysia", "region": "SEA",
    },
    # UAE — DFSA / ADX / DFM
    {
        "url": "https://news.google.com/rss/search?q=DFM+ADX+DIFC+company+office+property+announcement+UAE+2025&hl=en&gl=AE&ceid=AE:en",
        "exchange": "UAE_EXCHANGE", "country": "UAE", "region": "UAE",
    },
    # Japan — TSE
    {
        "url": "https://news.google.com/rss/search?q=Tokyo+Stock+Exchange+company+office+Japan+new+facility+2025&hl=en&gl=JP&ceid=JP:en",
        "exchange": "TSE", "country": "Japan", "region": "Japan",
    },
    # South Korea — KRX
    {
        "url": "https://news.google.com/rss/search?q=KRX+Korea+Exchange+company+office+new+headquarters+Seoul+2025&hl=en&gl=KR&ceid=KR:en",
        "exchange": "KRX", "country": "South Korea", "region": "Korea",
    },
]


def safe_get(session, url, **kwargs):
    try:
        resp = session.get(url, timeout=REQUEST_TIMEOUT, **kwargs)
        resp.raise_for_status()
        return resp
    except Exception as e:
        print(f"[GlobalExchange] Fetch error {url[:70]}: {e}")
        return None


class SECEdgarCrawler(BaseCrawler):
    """
    Crawls SEC EDGAR full-text search for CRE-relevant 8-K filings.
    Completely free, no API key required.
    """
    EDGAR_SEARCH = "https://efts.sec.gov/LATEST/search-index?q={query}&forms=8-K&dateRange=custom&startdt={date}&hits.hits.total.value=true&hits.hits._source.period_of_report=true"
    EDGAR_VIEWER = "https://www.sec.gov/cgi-bin/viewer?action=view&cik={cik}&type=8-K"

    QUERIES = [
        '"office space" "square feet"',
        '"office lease" "lease agreement"',
        '"new headquarters" "office"',
        '"data center" "facility" "lease"',
        '"warehouse" "distribution center" "lease"',
    ]

    def __init__(self):
        super().__init__(delay=2)
        self.session.headers.update({
            "User-Agent": "Nexus-Asia-CRE-Intel/1.0 contact@nexusasia.com",
            "Accept": "application/json",
        })

    def crawl(self, days_back: int = 3) -> list:
        articles = []
        start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

        for query in self.QUERIES[:3]:  # limit to 3 queries to avoid rate limiting
            try:
                url = f"https://efts.sec.gov/LATEST/search-index?q={query.replace(' ', '+')}&forms=8-K&dateRange=custom&startdt={start_date}"
                resp = safe_get(self.session, url)
                if not resp:
                    time.sleep(2)
                    continue

                data = resp.json()
                hits = data.get("hits", {}).get("hits", [])

                for hit in hits[:10]:
                    src = hit.get("_source", {})
                    company = src.get("entity_name", src.get("display_names", [""])[0] if src.get("display_names") else "")
                    filing_date = src.get("file_date", "")
                    form_type = src.get("form_type", "8-K")
                    accession = src.get("accession_no", "").replace("-", "")
                    cik = src.get("entity_id", "")

                    if not company:
                        continue

                    clean_query = query.replace('"', '')
                    headline = f"{company}: {form_type} filing — {clean_query}"
                    filing_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/"

                    articles.append({
                        "title": headline,
                        "text": f"SEC {form_type} filing by {company}. Keywords: {query}. Filed: {filing_date}",
                        "url": filing_url,
                        "source": "SEC_EDGAR",
                        "company_hint": company,
                        "published": filing_date,
                        "signal_type_hint": "FILING",
                        "exchange": "SEC_EDGAR",
                        "country": "USA",
                    })
                    print(f"[SEC_EDGAR] ✓ {company[:40]} | {form_type} | {filing_date}")

                time.sleep(1.5)

            except Exception as e:
                print(f"[SEC_EDGAR] Error on query '{query}': {e}")
                time.sleep(2)

        print(f"[SEC_EDGAR] Total: {len(articles)} filings")
        return articles


class GlobalExchangeGNewsCrawler(BaseCrawler):
    """
    Crawls Google News RSS for exchange filing signals globally.
    Works for LSE, SGX, HKEX, ASX, TSX, Bursa, UAE exchanges, TSE, KRX.
    """

    def __init__(self):
        super().__init__(delay=1)

    def crawl(self) -> list:
        import feedparser
        articles = []

        for feed_config in EXCHANGE_GNEWS_FEEDS:
            try:
                feed = feedparser.parse(feed_config["url"])
                exchange = feed_config["exchange"]
                country = feed_config["country"]
                region = feed_config["region"]

                for entry in feed.entries[:8]:
                    title = entry.get("title", "")
                    summary = entry.get("summary", "")
                    link = entry.get("link", "")
                    published = entry.get("published", "")

                    text = f"{title} {summary}".lower()

                    # Skip noise
                    if any(nk in text for nk in NOISE_KEYWORDS):
                        continue

                    # Must have CRE signal
                    if not any(kw in text for kw in CRE_KEYWORDS):
                        continue

                    articles.append({
                        "title": title,
                        "text": f"{title}. {summary}",
                        "url": link,
                        "source": f"EXCHANGE_{exchange}",
                        "company_hint": "",
                        "published": published,
                        "signal_type_hint": "FILING",
                        "exchange": exchange,
                        "country": country,
                        "region": region,
                    })
                    print(f"[{exchange}] ✓ {title[:60]}")

                time.sleep(0.5)

            except Exception as e:
                print(f"[GlobalExchange] Error {feed_config['exchange']}: {e}")

        print(f"[GlobalExchangeGNews] Total: {len(articles)} exchange signals")
        return articles


class GlobalREITCrawler(BaseCrawler):
    """
    Crawls global REIT and real estate fund announcements.
    Targets major listed REITs across India, Singapore, USA, Australia.
    """

    REIT_FEEDS = [
        # India REITs (Embassy, Mindspace, Brookfield, Nexus)
        {"url": "https://news.google.com/rss/search?q=Embassy+REIT+OR+Mindspace+REIT+OR+Brookfield+REIT+office+acquisition+lease&hl=en-IN&gl=IN&ceid=IN:en", "country": "India", "region": "India"},
        # Singapore REITs
        {"url": "https://news.google.com/rss/search?q=CapitaLand+Ascendas+REIT+office+Singapore+acquisition+lease+deal&hl=en&gl=SG&ceid=SG:en", "country": "Singapore", "region": "Singapore"},
        {"url": "https://news.google.com/rss/search?q=Keppel+REIT+Frasers+Mapletree+office+acquisition+Singapore&hl=en&gl=SG&ceid=SG:en", "country": "Singapore", "region": "Singapore"},
        # US REITs
        {"url": "https://news.google.com/rss/search?q=Boston+Properties+Vornado+SL+Green+office+REIT+deal+lease&hl=en&gl=US&ceid=US:en", "country": "USA", "region": "USA"},
        {"url": "https://news.google.com/rss/search?q=Prologis+Industrial+REIT+warehouse+lease+deal+acquisition&hl=en&gl=US&ceid=US:en", "country": "USA", "region": "USA"},
        # Australia REITs
        {"url": "https://news.google.com/rss/search?q=Dexus+GPT+Mirvac+REIT+office+Sydney+Melbourne+deal&hl=en&gl=AU&ceid=AU:en", "country": "Australia", "region": "Australia"},
        # UK REITs
        {"url": "https://news.google.com/rss/search?q=British+Land+Landsec+Segro+REIT+office+London+deal&hl=en&gl=GB&ceid=GB:en", "country": "UK", "region": "UK"},
        # Global
        {"url": "https://news.google.com/rss/search?q=REIT+acquisition+office+data+center+industrial+deal+2025&hl=en&gl=US&ceid=US:en", "country": "Global", "region": "Global"},
    ]

    def __init__(self):
        super().__init__(delay=1)

    def crawl(self) -> list:
        import feedparser
        articles = []

        for feed in self.REIT_FEEDS:
            try:
                parsed = feedparser.parse(feed["url"])
                for entry in parsed.entries[:6]:
                    title = entry.get("title", "")
                    summary = entry.get("summary", "")
                    link = entry.get("link", "")

                    articles.append({
                        "title": title,
                        "text": f"{title}. {summary}",
                        "url": link,
                        "source": "GLOBAL_REIT",
                        "company_hint": "",
                        "published": entry.get("published", ""),
                        "signal_type_hint": "LEASE",
                        "country": feed["country"],
                        "region": feed["region"],
                    })
                    print(f"[REIT] ✓ {title[:60]}")

                time.sleep(0.5)
            except Exception as e:
                print(f"[GlobalREIT] Error: {e}")

        print(f"[GlobalREIT] Total: {len(articles)} REIT signals")
        return articles


class GlobalDataCentreTracker(BaseCrawler):
    """
    Tracks global hyperscale and colocation data centre announcements.
    High-value CRE signal — DC = industrial lease + power + land.
    """

    DC_FEEDS = [
        {"url": "https://news.google.com/rss/search?q=data+centre+investment+facility+construction+India+2025&hl=en-IN&gl=IN&ceid=IN:en", "country": "India"},
        {"url": "https://news.google.com/rss/search?q=hyperscale+data+center+lease+construction+USA+2025&hl=en&gl=US&ceid=US:en", "country": "USA"},
        {"url": "https://news.google.com/rss/search?q=data+centre+Singapore+Malaysia+expansion+facility+2025&hl=en&gl=SG&ceid=SG:en", "country": "Singapore"},
        {"url": "https://news.google.com/rss/search?q=Microsoft+Google+Amazon+Apple+data+center+new+facility+2025&hl=en&gl=US&ceid=US:en", "country": "Global"},
        {"url": "https://news.google.com/rss/search?q=colocation+data+centre+UAE+Dubai+facility+expansion+2025&hl=en&gl=AE&ceid=AE:en", "country": "UAE"},
        {"url": "https://news.google.com/rss/search?q=data+centre+Australia+Sydney+Melbourne+expansion+2025&hl=en&gl=AU&ceid=AU:en", "country": "Australia"},
        {"url": "https://news.google.com/rss/search?q=data+centre+UK+London+new+facility+hyperscale+2025&hl=en&gl=GB&ceid=GB:en", "country": "UK"},
    ]

    def __init__(self):
        super().__init__(delay=1)

    def crawl(self) -> list:
        import feedparser
        articles = []

        for feed in self.DC_FEEDS:
            try:
                parsed = feedparser.parse(feed["url"])
                for entry in parsed.entries[:5]:
                    title = entry.get("title", "")
                    summary = entry.get("summary", "")
                    articles.append({
                        "title": title,
                        "text": f"{title}. {summary}",
                        "url": entry.get("link", ""),
                        "source": "DATA_CENTRE_TRACKER",
                        "company_hint": "",
                        "published": entry.get("published", ""),
                        "signal_type_hint": "DATA CENTRE",
                        "country": feed["country"],
                        "region": feed["country"],
                    })
                    print(f"[DC_TRACKER] ✓ {title[:60]}")
                time.sleep(0.5)
            except Exception as e:
                print(f"[DCTracker] Error: {e}")

        print(f"[GlobalDCTracker] Total: {len(articles)} DC signals")
        return articles
