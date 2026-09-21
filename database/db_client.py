import os
from supabase import create_client, Client
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def get_client() -> Client:
    url = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")
    return create_client(url, key)

def upsert_company(client: Client, company_name: str, country: str = "India") -> str:
    from nlp.text_cleaner import normalize_company_name
    normalized = normalize_company_name(company_name)
    result = client.table("companies").upsert({
        "company_name":    company_name,
        "normalized_name": normalized,
        "country":         country,
    }, on_conflict="normalized_name").execute()
    if result.data:
        return result.data[0]["company_id"]
    existing = client.table("companies").select("company_id")\
        .eq("normalized_name", normalized).execute()
    return existing.data[0]["company_id"]

def insert_signal(client: Client, company_id: str, signal: dict) -> str:
    """
    Persist signals — NEVER delete. Dedup by source_url + company_id.
    New articles = new rows. Same article recrawled = skip.
    """
    confidence_val = signal.get("confidence") if "confidence" in signal \
                     else signal.get("confidence_score", 0)
    source_url = signal.get("source_url", "")

    # Dedup check — same article + same company = skip
    if source_url:
        existing = client.table("signals")\
            .select("signal_id")\
            .eq("source_url", source_url)\
            .eq("company_id", company_id)\
            .limit(1).execute()
        if existing.data:
            return existing.data[0]["signal_id"]

    result = client.table("signals").insert({
        "company_id":       company_id,
        "signal_type":      signal.get("signal_type", "OFFICE"),
        "space_type":       signal.get("space_type"),
        "location":         signal.get("location", "India"),
        "country":          signal.get("country", "India"),
        "region":           signal.get("region", "India"),
        "confidence_score": int(confidence_val or 0),
        "urgency":          signal.get("urgency", "MEDIUM"),
        "summary":          signal.get("summary", "")[:500],
        "why_cre":          signal.get("why_cre", "")[:300],
        "source_url":       source_url,
        "data_source":      signal.get("data_source", "RSS"),
        "published_at":     signal.get("published_at"),
        "funding_amount":   signal.get("funding_amount"),
        "funding_round":    signal.get("funding_round"),
        "headcount":        signal.get("headcount"),
        "sqft":             signal.get("sqft"),
    }).execute()
    return result.data[0]["signal_id"]

def upsert_lead_score(client: Client, company_id: str, score_data: dict):
    score_data.pop("breakdown", None)
    score_data.pop("top_signal", None)
    client.table("lead_scores").upsert({
        "company_id": company_id,
        **score_data
    }, on_conflict="company_id").execute()
