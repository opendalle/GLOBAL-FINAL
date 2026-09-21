"""
Intel Crawlers — Nexus Asia CRE Intelligence
=============================================
Tracks:
  1. MCA — new incorporations, subsidiaries, SPICe filings
  2. RERA — commercial project registrations (supply pipeline)
  3. LinkedIn/Hiring — job surge signals (demand proxy)
  4. Distress — NCLT, IBC, NPA, sublease, downsizing
  5. Lease Expiry — renewal windows, vacating news

All via Google News RSS — free, zero-block, no API keys needed.
"""

import time
from datetime import datetime, timezone, timedelta
from crawler.base_crawler import BaseCrawler
from crawler.rss_crawler import _parse_published

MAX_AGE_HOURS = 72

# ── MCA SIGNALS ───────────────────────────────────────────────────────────────

MCA_GNEWS_QUERIES = [
    {
        "url": "https://news.google.com/rss/search?q=new+subsidiary+india+incorporated+office+2026&hl=en-IN&gl=IN&ceid=IN:en",
        "label": "MCA_NEW_SUBSIDIARY",
        "signal_hint": "EXPAND",
        "confidence_boost": 20,
        "why": "New subsidiary in India — registered office + operational space required immediately",
    },
    {
        "url": "https://news.google.com/rss/search?q=company+incorporated+india+new+entity+headquarters&hl=en-IN&gl=IN&ceid=IN:en",
        "label": "MCA_INCORPORATION",
        "signal_hint": "OFFICE",
        "confidence_boost": 20,
        "why": "New company incorporated — registered office mandatory under Companies Act within 30 days",
    },
    {
        "url": "https://news.google.com/rss/search?q=india+wholly+owned+subsidiary+setup+operations&hl=en-IN&gl=IN&ceid=IN:en",
        "label": "MCA_WOS",
        "signal_hint": "EXPAND",
        "confidence_boost": 25,
        "why": "Wholly-owned subsidiary set up — typically 5,000-50,000 sqft first office required",
    },
    {
        "url": "https://news.google.com/rss/search?q=SPICe+form+company+registration+india+new+office&hl=en-IN&gl=IN&ceid=IN:en",
        "label": "MCA_SPICE",
        "signal_hint": "OFFICE",
        "confidence_boost": 15,
        "why": "SPICe form filing = new company registration — office needed",
    },
]

# ── RERA SIGNALS ──────────────────────────────────────────────────────────────

RERA_GNEWS_QUERIES = [
    {
        "url": "https://news.google.com/rss/search?q=RERA+registered+commercial+office+project+india+2026&hl=en-IN&gl=IN&ceid=IN:en",
        "label": "RERA_COMMERCIAL",
        "signal_hint": "OFFICE",
        "confidence_boost": 15,
        "why": "New RERA-registered commercial project — upcoming supply entering market",
    },
    {
        "url": "https://news.google.com/rss/search?q=MahaRERA+commercial+project+registration+mumbai+pune&hl=en-IN&gl=IN&ceid=IN:en",
        "label": "RERA_MAHARERA",
        "signal_hint": "OFFICE",
        "confidence_boost": 15,
        "why": "MahaRERA commercial registration — new Grade A supply in Mumbai/Pune pipeline",
    },
    {
        "url": "https://news.google.com/rss/search?q=RERA+office+space+launch+bangalore+hyderabad+chennai&hl=en-IN&gl=IN&ceid=IN:en",
        "label": "RERA_SOUTH",
        "signal_hint": "OFFICE",
        "confidence_boost": 15,
        "why": "RERA office launch in South India — upcoming supply, potential pre-lease opportunity",
    },
    {
        "url": "https://news.google.com/rss/search?q=RERA+project+registered+delhi+NCR+gurugram+noida+office&hl=en-IN&gl=IN&ceid=IN:en",
        "label": "RERA_NCR",
        "signal_hint": "OFFICE",
        "confidence_boost": 15,
        "why": "RERA-registered office project in Delhi NCR — new supply entering pipeline",
    },
    {
        "url": "https://news.google.com/rss/search?q=pre-leased+commercial+asset+RERA+developer+india&hl=en-IN&gl=IN&ceid=IN:en",
        "label": "RERA_PRELEASED",
        "signal_hint": "LEASE",
        "confidence_boost": 20,
        "why": "Pre-leased commercial asset registered — confirmed tenant demand, deal in pipeline",
    },
]

# ── LINKEDIN / HIRING SIGNALS ─────────────────────────────────────────────────

LINKEDIN_GNEWS_QUERIES = [
    {
        "url": "https://news.google.com/rss/search?q=company+hiring+100+employees+india+expansion+office&hl=en-IN&gl=IN&ceid=IN:en",
        "label": "HIRING_SURGE_100",
        "signal_hint": "HIRING",
        "confidence_boost": 15,
        "why": "100+ hiring in India — office expansion likely within 6-12 months",
    },
    {
        "url": "https://news.google.com/rss/search?q=company+hiring+500+1000+employees+india+bengaluru+mumbai&hl=en-IN&gl=IN&ceid=IN:en",
        "label": "HIRING_SURGE_500",
        "signal_hint": "HIRING",
        "confidence_boost": 25,
        "why": "500-1000 employee surge — large Grade A office requirement imminent",
    },
    {
        "url": "https://news.google.com/rss/search?q=headcount+doubling+india+team+expansion+workspace&hl=en-IN&gl=IN&ceid=IN:en",
        "label": "HEADCOUNT_DOUBLE",
        "signal_hint": "EXPAND",
        "confidence_boost": 20,
        "why": "Headcount doubling — current office insufficient, space review triggered",
    },
    {
        "url": "https://news.google.com/rss/search?q=GCC+hiring+india+1000+jobs+global+capability+centre&hl=en-IN&gl=IN&ceid=IN:en",
        "label": "GCC_HIRING",
        "signal_hint": "EXPAND",
        "confidence_boost": 30,
        "why": "GCC hiring at scale — 1000+ seats required, Grade A office mandatory",
    },
    {
        "url": "https://news.google.com/rss/search?q=%22facilities+manager%22+OR+%22workplace+manager%22+hiring+india+bengaluru+OR+pune+OR+mumbai&hl=en-IN&gl=IN&ceid=IN:en",
        "label": "FACILITIES_HIRE",
        "signal_hint": "HIRING",
        "confidence_boost": 35,
        "why": "Hiring facilities/workplace manager = physical office being set up NOW",
    },
    {
        "url": "https://news.google.com/rss/search?q=%22head+of+real+estate%22+OR+%22real+estate+manager%22+hiring+india+2026&hl=en-IN&gl=IN&ceid=IN:en",
        "label": "RE_HEAD_HIRE",
        "signal_hint": "HIRING",
        "confidence_boost": 40,
        "why": "Hiring Head of Real Estate = large office portfolio being built — top-tier lead",
    },
    {
        "url": "https://news.google.com/rss/search?q=%22setting+up%22+%22india+office%22+GCC+2026+bengaluru+OR+pune+OR+hyderabad&hl=en-IN&gl=IN&ceid=IN:en",
        "label": "GCC_SETUP_2026",
        "signal_hint": "EXPAND",
        "confidence_boost": 35,
        "why": "Company setting up India GCC in 2026 — 10k-50k sqft Grade A demand",
    },
    {
        "url": "https://news.google.com/rss/search?q=%22global+capability+centre%22+india+%22new+office%22+2026&hl=en-IN&gl=IN&ceid=IN:en",
        "label": "GCC_NEW_OFFICE",
        "signal_hint": "OFFICE",
        "confidence_boost": 35,
        "why": "New GCC office in India 2026 — active space requirement",
    },
    {
        "url": "https://news.google.com/rss/search?q=%22india+expansion%22+%22new+office%22+2026+bengaluru+OR+pune+OR+hyderabad+OR+mumbai&hl=en-IN&gl=IN&ceid=IN:en",
        "label": "INDIA_EXPANSION_2026",
        "signal_hint": "EXPAND",
        "confidence_boost": 30,
        "why": "Direct India expansion + city mention — hot lead for office leasing",
    },
    {
        "url": "https://news.google.com/rss/search?q=foreign+company+%22india+entry%22+OR+%22india+launch%22+office+2026&hl=en-IN&gl=IN&ceid=IN:en",
        "label": "FOREIGN_INDIA_ENTRY",
        "signal_hint": "OFFICE",
        "confidence_boost": 30,
        "why": "Foreign company entering India — registered office + operational space needed",
    },
]

# ── DISTRESS SIGNALS ──────────────────────────────────────────────────────────

DISTRESS_GNEWS_QUERIES = [
    {
        "url": "https://news.google.com/rss/search?q=NCLT+insolvency+resolution+real+estate+india+office&hl=en-IN&gl=IN&ceid=IN:en",
        "label": "DISTRESS_NCLT",
        "signal_hint": "DISTRESS",
        "why": "NCLT insolvency — potential office space surrender, distressed asset opportunity",
    },
    {
        "url": "https://news.google.com/rss/search?q=company+downsizing+layoffs+india+office+sublease&hl=en-IN&gl=IN&ceid=IN:en",
        "label": "DISTRESS_SUBLEASE",
        "signal_hint": "DISTRESS",
        "why": "Downsizing/layoffs — office space likely to be sublet or surrendered",
    },
    {
        "url": "https://news.google.com/rss/search?q=NPA+stressed+developer+india+commercial+project+lender&hl=en-IN&gl=IN&ceid=IN:en",
        "label": "DISTRESS_NPA",
        "signal_hint": "DISTRESS",
        "why": "NPA/stressed developer — distressed commercial asset, motivated seller/lender",
    },
    {
        "url": "https://news.google.com/rss/search?q=IBC+resolution+commercial+property+india+auction&hl=en-IN&gl=IN&ceid=IN:en",
        "label": "DISTRESS_IBC",
        "signal_hint": "DISTRESS",
        "why": "IBC resolution — commercial property going to auction, acquisition opportunity",
    },
]

# ── LEASE EXPIRY SIGNALS ──────────────────────────────────────────────────────

LEASE_EXPIRY_QUERIES = [
    {
        "url": "https://news.google.com/rss/search?q=company+lease+renewal+office+india+2025+2026&hl=en-IN&gl=IN&ceid=IN:en",
        "label": "LEASE_RENEWAL",
        "why": "Lease renewal news — active negotiation, brokerage opportunity",
    },
    {
        "url": "https://news.google.com/rss/search?q=company+vacating+office+india+moving+new+location&hl=en-IN&gl=IN&ceid=IN:en",
        "label": "OFFICE_VACATING",
        "why": "Company vacating office — space available + mover needs new space",
    },
    {
        "url": "https://news.google.com/rss/search?q=office+lease+expiry+india+commercial+renewal+notice&hl=en-IN&gl=IN&ceid=IN:en",
        "label": "LEASE_EXPIRY",
        "why": "Lease expiry signal — active renewal window, approach with alternatives",
    },
]

DISTRESS_KEYWORDS = [
    "nclt", "insolvency", "ibc", "resolution professional",
    "npa", "stressed asset", "lender takes over",
    "sublease", "sub-lease", "downsizing", "layoff",
    "office closure", "vacating", "surrender",
    "auction", "e-auction", "distressed", "haircut",
    "liquidation", "winding up",
]


def _parse_feed(queries: list, source_tag: str, signal_hint: str = None, urgency_hint: str = None) -> list:
    import feedparser
    articles = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)
    for q in queries:
        try:
            feed = feedparser.parse(q["url"])
            fresh = 0
            stale = 0
            for entry in feed.entries:
                pub = _parse_published(entry)
                if pub < cutoff:
                    stale += 1
                    continue
                article = {
                    "title": entry.get("title", ""),
                    "text": entry.get("summary", entry.get("title", "")),
                    "url": entry.get("link", ""),
                    "published": pub.isoformat(),
                    "published_at": pub.isoformat(),
                    "source": q["label"],
                    "signal_type_hint": q.get("signal_hint", signal_hint or "OFFICE"),
                    "confidence_boost": q.get("confidence_boost", 0),
                    "why_cre_hint": q.get("why", ""),
                    "region": "India",
                    "country": "India",
                }
                if urgency_hint:
                    article["urgency_hint"] = urgency_hint
                articles.append(article)
                fresh += 1
            print(f"[{source_tag}] {q['label']}: {fresh} fresh, {stale} stale dropped")
            time.sleep(0.5)
        except Exception as e:
            print(f"[{source_tag}] {q['label']} error: {e}")
    return articles


class MCAIntelCrawler(BaseCrawler):
    """Tracks MCA incorporations and RERA registrations via Google News RSS."""

    def __init__(self):
        super().__init__(delay=1)

    def crawl(self) -> list:
        articles = _parse_feed(MCA_GNEWS_QUERIES, "MCAIntel")
        articles += _parse_feed(RERA_GNEWS_QUERIES, "RERAIntel")
        print(f"[MCAIntelCrawler] Total: {len(articles)} articles")
        return articles


class HiringIntelCrawler(BaseCrawler):
    """
    Tracks hiring surges as proxy CRE demand signals.
    LinkedIn blocks direct scraping — Google News captures the same stories.
    Includes high-signal role hiring (Facilities Mgr, Head of RE) for strongest leads.
    """

    def __init__(self):
        super().__init__(delay=1)

    def crawl(self) -> list:
        articles = _parse_feed(LINKEDIN_GNEWS_QUERIES, "HiringIntel")
        print(f"[HiringIntelCrawler] Total: {len(articles)} hiring signals")
        return articles


class DistressRadarCrawler(BaseCrawler):
    """
    Distress signal crawler — NCLT, IBC, NPA, sublease, downsizing.
    Moat signal — competitors don't track this proactively.
    """

    def __init__(self):
        super().__init__(delay=1)

    def crawl(self) -> list:
        import feedparser
        articles = []
        for q in DISTRESS_GNEWS_QUERIES:
            try:
                feed = feedparser.parse(q["url"])
                hits = 0
                for entry in feed.entries:
                    text = (entry.get("title", "") + " " + entry.get("summary", "")).lower()
                    if any(kw in text for kw in DISTRESS_KEYWORDS):
                        articles.append({
                            "title": entry.get("title", ""),
                            "text": entry.get("summary", entry.get("title", "")),
                            "url": entry.get("link", ""),
                            "published": entry.get("published", datetime.utcnow().isoformat()),
                            "source": q["label"],
                            "signal_type_hint": "DISTRESS",
                            "confidence_boost": 0,
                            "why_cre_hint": q["why"],
                            "region": "India",
                            "country": "India",
                            "urgency_hint": "HIGH",
                        })
                        hits += 1
                print(f"[DistressRadar] {q['label']}: {len(feed.entries)} raw → {hits} distress hits")
                time.sleep(0.5)
            except Exception as e:
                print(f"[DistressRadar] {q['label']} error: {e}")
        print(f"[DistressRadarCrawler] Total: {len(articles)} distress signals")
        return articles


class LeaseExpiryTracker(BaseCrawler):
    """
    Proxy lease expiry tracker — renewal windows, vacating news.
    No direct lease DB access; Google News catches the same events.
    """

    def __init__(self):
        super().__init__(delay=1)

    def crawl(self) -> list:
        articles = _parse_feed(LEASE_EXPIRY_QUERIES, "LeaseExpiry", signal_hint="LEASE", urgency_hint="HIGH")
        print(f"[LeaseExpiryTracker] Total: {len(articles)} lease signals")
        return articles
