"""
NEXUS PROP INTEL v4.1 — Global CRE Intelligence Pipeline | Bloomberg for CRE
Powered by Gemini AI NLP + Telegram Alerts
=========================================================
Tier 1 upgrade:
- MCA intelligence (new incorporations, subsidiaries)
- RERA project tracking (new supply pipeline)
- Hiring surge tracker (proxy demand signals)
- Distress radar (NCLT/IBC/NPA/sublease)
- Lease expiry tracker
- Signals persist forever (no wipe)
- Dedup by source_url
"""
import json
import os
from crawler.rss_crawler import RSSCrawler
from crawler.news_crawler import NewsCrawler
from crawler.primary_sources import BSECrawler, FilingPDFCrawler, LinkedInSignalCrawler
from crawler.intel_crawlers import MCAIntelCrawler, HiringIntelCrawler, DistressRadarCrawler, LeaseExpiryTracker
from nlp.cre_filter import is_cre_relevant, get_signal_type
from nlp.cre_intent import analyze_cre_intent, detect_country, detect_region
from nlp.entity_extractor import extract_entities
from nlp.signal_classifier import classify_signal, extract_summary
from nlp.text_cleaner import clean_text, deduplicate
from nlp.enrichment import enrich_signal
from scoring.lead_scorer import compute_lead_score
from database.db_client import get_client, upsert_company, insert_signal, upsert_lead_score
from crawler.global_exchange_crawler import SECEdgarCrawler, GlobalExchangeGNewsCrawler, GlobalREITCrawler, GlobalDataCentreTracker
from nlp.gemini_nlp import gemini_extract_signal, batch_extract_signals
from crawler.telegram_alerts import send_signal_alert, send_startup_message, send_completion_message

with open("config/sources.json") as f:
    SOURCES = json.load(f)

JUNK_NAMES = [
    "href=", "&#", "cin:", "dalal street", "5th floor", "limited cin",
    "stock exchange", "bse limited", "nse limited", "listing department",
    "p.j. tower", "g-block", "g block", "khasra", "plot ", "kisl/",
    "assemblies limited", "compliance officer", "color=", "font size",
    "unknown company",
]


def build_signal(signal_type, summary, source_url, location, confidence,
                 data_source, why_cre="", urgency="MEDIUM",
                 country="India", region="India"):
    return {
        "signal_type": str(signal_type or "OFFICE").upper(),
        "summary":     str(summary or "")[:500],
        "source_url":  str(source_url or ""),
        "location":    str(location or "India"),
        "confidence":  min(max(int(confidence or 0), 0), 100),
        "data_source": str(data_source or "RSS"),
        "why_cre":     str(why_cre or "")[:300],
        "urgency":     str(urgency or "MEDIUM"),
        "country":     str(country or "India"),
        "region":      str(region or "India"),
        "space_type":  None,
    }


def save_signal(client, company_name, signal, company_signals):
    if not company_name or len(company_name.strip()) < 3:
        return False
    if any(j in company_name.lower() for j in JUNK_NAMES):
        return False
    try:
        cid = upsert_company(client, company_name.strip(), signal.get("country", "India"))
        insert_signal(client, cid, signal)
        print(f"[DB] ✓ {company_name[:32]:<32} | {signal['signal_type']:<10} | "
              f"conf:{signal['confidence']:>3} | {signal['urgency']:<6} | "
              f"{signal['country']:<12} | {signal['location'][:18]}")
        # Telegram alert for high-priority signals
        send_signal_alert(company_name, signal)
        company_signals.setdefault(cid, []).append(signal)
        return True
    except Exception as e:
        print(f"[DB] ERR {company_name[:30]}: {e}")
        return False


def run_pipeline():
    client = get_client()
    try:
        client.table("companies").select("company_id").limit(1).execute()
        print("[Pipeline] ✓ Supabase connected — persistent mode")
    except Exception as e:
        print(f"[Pipeline] SUPABASE FAILED: {e}")
        return

    all_articles  = []
    source_counts = {}

    # ── TIER 1: Primary Exchange Filings ─────────────────────────────────────
    for name, fn in [
        ("BSE",      lambda: BSECrawler().crawl(days_back=2)),
        ("NSE",      lambda: FilingPDFCrawler().crawl_nse_announcements(days_back=3)),
        ("LINKEDIN", lambda: LinkedInSignalCrawler().crawl(min_jobs=15)),
    ]:
        print(f"\n[Pipeline] === {name} ===")
        try:
            arts = fn()
            for a in arts:
                a.setdefault("region", "India")
                a.setdefault("country", "India")
            all_articles.extend(arts)
            source_counts[name] = len(arts)
        except Exception as e:
            print(f"[Pipeline] {name} error: {e}")
            source_counts[name] = 0

    # ── TIER 1: MCA Intelligence (incorporations, subsidiaries) ──────────────
    print("\n[Pipeline] === MCA Intelligence ===")
    try:
        mca_arts = MCAIntelCrawler().crawl()
        for a in mca_arts:
            a["text"] = a.get("summary", "") + " " + a.get("title", "")
        all_articles.extend(mca_arts)
        source_counts["MCA"] = len(mca_arts)
    except Exception as e:
        print(f"[Pipeline] MCA error: {e}")
        source_counts["MCA"] = 0

    # ── TIER 1: Hiring Surge Tracker ─────────────────────────────────────────
    print("\n[Pipeline] === Hiring Intel ===")
    try:
        hiring_arts = HiringIntelCrawler().crawl()
        for a in hiring_arts:
            a["text"] = a.get("summary", "") + " " + a.get("title", "")
        all_articles.extend(hiring_arts)
        source_counts["HIRING"] = len(hiring_arts)
    except Exception as e:
        print(f"[Pipeline] Hiring error: {e}")
        source_counts["HIRING"] = 0

    # ── TIER 1: Distress Radar ────────────────────────────────────────────────
    print("\n[Pipeline] === Distress Radar ===")
    try:
        distress_arts = DistressRadarCrawler().crawl()
        for a in distress_arts:
            a["text"] = a.get("summary", "") + " " + a.get("title", "")
        all_articles.extend(distress_arts)
        source_counts["DISTRESS"] = len(distress_arts)
    except Exception as e:
        print(f"[Pipeline] Distress error: {e}")
        source_counts["DISTRESS"] = 0

    # ── TIER 1: Lease Expiry Tracker ──────────────────────────────────────────
    print("\n[Pipeline] === Lease Expiry Tracker ===")
    try:
        expiry_arts = LeaseExpiryTracker().crawl()
        for a in expiry_arts:
            a["text"] = a.get("summary", "") + " " + a.get("title", "")
        all_articles.extend(expiry_arts)
        source_counts["LEASE_EXPIRY"] = len(expiry_arts)
    except Exception as e:
        print(f"[Pipeline] LeaseExpiry error: {e}")
        source_counts["LEASE_EXPIRY"] = 0

    # ── Standard RSS ──────────────────────────────────────────────────────────
    print("\n[Pipeline] === RSS Feeds ===")
    try:
        rss_urls = [f["url"] if isinstance(f, dict) else f for f in SOURCES["rss_feeds"]]
        rss_meta = {(f["url"] if isinstance(f, dict) else f): f for f in SOURCES["rss_feeds"]}
        rss_raw  = RSSCrawler().crawl(rss_urls)
        for a in rss_raw:
            a["text"]   = a.get("summary", "") + " " + a.get("title", "")
            meta        = rss_meta.get(a.get("source", ""), {})
            a["region"] = meta.get("region", "India") if isinstance(meta, dict) else "India"
            a["country"]= meta.get("country", "India") if isinstance(meta, dict) else "India"
        all_articles.extend(rss_raw)
        source_counts["RSS"] = len(rss_raw)
    except Exception as e:
        print(f"[Pipeline] RSS error: {e}")
        source_counts["RSS"] = 0

    # ── Google News RSS — Global ──────────────────────────────────────────────
    print("\n[Pipeline] === Google News RSS (Global) ===")
    try:
        gnews_feeds  = [f["url"] for f in SOURCES.get("google_news_rss", [])]
        gnews_meta   = {f["url"]: f for f in SOURCES.get("google_news_rss", [])}
        gnews_raw    = RSSCrawler().crawl(gnews_feeds)
        for a in gnews_raw:
            a["text"]    = a.get("summary", "") + " " + a.get("title", "")
            feed_url     = a.get("source", "")
            meta         = gnews_meta.get(feed_url, {})
            a["source"]  = f"GNEWS_{meta.get('label','GOOGLE').upper().replace(' ','_')}"
            a["region"]  = meta.get("region", "India")
            a["country"] = meta.get("country", "India")
        all_articles.extend(gnews_raw)
        source_counts["GNEWS"] = len(gnews_raw)
        print(f"[Pipeline] Google News: {len(gnews_raw)} from {len(gnews_feeds)} queries")
    except Exception as e:
        print(f"[Pipeline] Google News error: {e}")
        source_counts["GNEWS"] = 0


    # ── GLOBAL: SEC EDGAR (USA) ───────────────────────────────────────────────
    print("\n[Pipeline] === SEC EDGAR (USA) ===")
    try:
        sec_arts = SECEdgarCrawler().crawl(days_back=3)
        for a in sec_arts:
            a.setdefault("region", "USA")
            a.setdefault("country", "USA")
        all_articles.extend(sec_arts)
        source_counts["SEC_EDGAR"] = len(sec_arts)
    except Exception as e:
        print(f"[Pipeline] SEC_EDGAR error: {e}")
        source_counts["SEC_EDGAR"] = 0

    # ── GLOBAL: Exchange Filing Signals (LSE/SGX/HKEX/ASX/TSX/etc) ───────────
    print("\n[Pipeline] === Global Exchange Signals ===")
    try:
        gex_arts = GlobalExchangeGNewsCrawler().crawl()
        all_articles.extend(gex_arts)
        source_counts["GLOBAL_EXCHANGE"] = len(gex_arts)
    except Exception as e:
        print(f"[Pipeline] GlobalExchange error: {e}")
        source_counts["GLOBAL_EXCHANGE"] = 0

    # ── GLOBAL: REIT Tracker ──────────────────────────────────────────────────
    print("\n[Pipeline] === Global REIT Tracker ===")
    try:
        reit_arts = GlobalREITCrawler().crawl()
        all_articles.extend(reit_arts)
        source_counts["GLOBAL_REIT"] = len(reit_arts)
    except Exception as e:
        print(f"[Pipeline] GlobalREIT error: {e}")
        source_counts["GLOBAL_REIT"] = 0

    # ── GLOBAL: Data Centre Tracker ───────────────────────────────────────────
    print("\n[Pipeline] === Global Data Centre Tracker ===")
    try:
        dc_arts = GlobalDataCentreTracker().crawl()
        all_articles.extend(dc_arts)
        source_counts["GLOBAL_DC"] = len(dc_arts)
    except Exception as e:
        print(f"[Pipeline] GlobalDC error: {e}")
        source_counts["GLOBAL_DC"] = 0

    # ── Deduplicate ───────────────────────────────────────────────────────────
    all_articles = deduplicate(all_articles, key="url")
    print(f"\n[Pipeline] Total unique articles: {len(all_articles)}")
    print(f"[Pipeline] By source: {source_counts}\n")

    # ── Gemini AI Extraction (replaces spaCy for non-tier1 articles) ───────────
    USE_GEMINI = bool(os.environ.get("GEMINI_API_KEY", "AIzaSyCk_J6g8rovloY0N9PtnNUaJoon4nIYjDQ"))
    if USE_GEMINI:
        print("\n[Pipeline] === Gemini AI NLP Extraction ===")
        # Only run Gemini on non-tier1 articles (tier1 are pre-classified)
        non_tier1 = [a for a in all_articles if not any(
            s in a.get("source","") for s in ["BSE","NSE","MCA_","RERA_","HIRING_","DISTRESS_","LEASE_","SEC_EDGAR","EXCHANGE_","GLOBAL_REIT","DATA_CENTRE"]
        )]
        tier1_arts = [a for a in all_articles if a not in non_tier1]
        
        print(f"[Gemini] Running on {len(non_tier1)} articles (tier1={len(tier1_arts)} bypass)")
        gemini_results = batch_extract_signals(non_tier1[:150])  # cap at 150 to save quota
        
        # Attach Gemini results back to articles
        for article, gresult in gemini_results:
            article["_gemini"] = gresult
        
        print(f"[Gemini] Got {len(gemini_results)} CRE signals from {len(non_tier1)} articles")
    
    send_startup_message(len(all_articles))

    stats = {"seen":0, "intent":0, "direct":0, "tier1":0, "rejected":0, "saved":0, "high_priority":0}
    company_signals = {}

    for article in all_articles:
        stats["seen"] += 1
        title    = article.get("title", "")
        text     = clean_text(article.get("text", ""))
        combined = (title + " " + text).strip()
        if len(combined) < 30:
            stats["rejected"] += 1
            continue

        source      = article.get("source", "RSS")
        is_primary  = any(s in source for s in ["BSE", "NSE", "LINKEDIN"])
        is_tier1    = any(s in source for s in ["MCA_", "RERA_", "HIRING_", "HEADCOUNT_",
                                                 "GCC_HIRING", "DISTRESS_", "LEASE_RENEWAL",
                                                 "OFFICE_VACATING", "LEASE_EXPIRY",
                                                 "SEC_EDGAR", "EXCHANGE_", "GLOBAL_REIT", "DATA_CENTRE_TRACKER"])
        art_region  = article.get("region", "India")
        art_country = article.get("country", "India")

        # Use Gemini result if available (much better accuracy)
        gemini = article.get("_gemini")
        if gemini:
            if not gemini.get("is_cre_relevant", True):
                stats["rejected"] += 1
                continue
            # Override entity extraction with Gemini's superior results
            if gemini.get("company_name"):
                companies = [gemini["company_name"]]
            else:
                companies = []
            if gemini.get("location"):
                location = gemini["location"]
            else:
                location = article.get("location_hint", "India")
            if gemini.get("country"):
                final_country = gemini["country"]
            if gemini.get("region"):
                final_region = gemini["region"]
        else:
            entities  = extract_entities(combined)
        if not article.get("_gemini"):
            location  = entities["locations"][0] if entities["locations"] else article.get("location_hint", "India")
            companies = entities["companies"] or ([article["company_hint"]] if article.get("company_hint") else [])

        content_country = detect_country(combined)
        content_region  = detect_region(combined, art_region)
        final_country   = content_country if content_country != "India" or art_country == "India" else art_country
        final_region    = content_region

        signal = None

        # TIER 1 signals — pre-classified, high confidence, bypass filter
        if is_tier1:
            sig_type  = article.get("signal_type_hint", "OFFICE")
            why       = article.get("why_cre_hint", "")
            urgency   = article.get("urgency_hint", "MEDIUM")
            base_conf = 65
            if "DISTRESS" in source:
                base_conf = 75
                urgency   = "HIGH"
            elif "GCC_HIRING" in source or "HIRING_SURGE_500" in source:
                base_conf = 72
                urgency   = "HIGH"
            elif "LEASE" in source:
                base_conf = 70
                urgency   = "HIGH"
            elif "MCA_WOS" in source or "MCA_INCORPORATION" in source:
                base_conf = 68

            base_conf += article.get("confidence_boost", 0)
            signal = build_signal(
                sig_type,
                why + " | " + extract_summary(combined, []),
                article.get("url", ""), location,
                min(base_conf, 95), source,
                why_cre=why, urgency=urgency,
                country=final_country, region=final_region,
            )
            stats["tier1"] += 1
            print(f"[Tier1] ◆ {title[:70]}")
            print(f"        → {why[:80]}")

        # Intent layer — GCC, funding, foreign entry, growth
        if signal is None:
            intent = analyze_cre_intent(title, combined, location)
            if intent:
                why    = intent.get("why_cre", "")
                signal = build_signal(
                    intent["signal_type"],
                    why + " | " + extract_summary(combined, []),
                    article.get("url", ""), location,
                    intent["confidence_score"], source,
                    why_cre=why, urgency=intent.get("urgency", "MEDIUM"),
                    country=intent.get("country", final_country),
                    region=final_region,
                )
                stats["intent"] += 1
                print(f"[Intent] ★ {title[:70]}")
                print(f"         → {why[:80]}")

        # Primary source (BSE/NSE)
        if signal is None and is_primary:
            sig_type = article.get("signal_type_hint") or get_signal_type(title, text)
            signal   = build_signal(
                sig_type, extract_summary(combined, []),
                article.get("url", ""), location, 70, source,
                country=final_country, region=final_region,
            )
            stats["direct"] += 1

        # CRE keyword filter + classifier
        if signal is None:
            relevant, confidence, reason = is_cre_relevant(title, text)
            if relevant:
                classified = classify_signal(article)
                if classified:
                    signal = build_signal(
                        classified.get("signal_type", "OFFICE"),
                        extract_summary(combined, classified.get("matched_phrases", [])),
                        article.get("url", ""), location,
                        classified.get("confidence_score", int(confidence * 100)), source,
                        country=final_country, region=final_region,
                    )
                    stats["direct"] += 1
            if signal is None:
                stats["rejected"] += 1
                continue

        # Enrich signal with funding amount, headcount, sqft, timeline
        if signal:
            signal = enrich_signal(signal, article)

        # Save
        for co in (companies or ["Unknown Company"])[:2]:
            if save_signal(client, co, signal, company_signals):
                stats["saved"] += 1

    # Score all companies
    print(f"\n[Pipeline] Scoring {len(company_signals)} companies...")
    for cid, sigs in company_signals.items():
        try:
            score_data = compute_lead_score(sigs)
            upsert_lead_score(client, cid, score_data)
        except Exception as e:
            print(f"[Scoring] {cid}: {e}")

    total = stats["intent"] + stats["direct"] + stats["tier1"]
    print(f"""
[Pipeline] ════ COMPLETE ════
  Articles seen     : {stats['seen']}
  Tier 1 intel      : {stats['tier1']}   (MCA/RERA/Hiring/Distress/LeaseExpiry)
  Intent leads      : {stats['intent']}   (funding/GCC/foreign entry/growth)
  Direct CRE        : {stats['direct']}   (explicit space keywords)
  Rejected          : {stats['rejected']}
  Saved to DB       : {stats['saved']}
  Companies scored  : {len(company_signals)}
  Capture rate      : {round(total/max(stats['seen'],1)*100,1)}%
""")


if __name__ == "__main__":
    run_pipeline()
