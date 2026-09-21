"""
Gemini NLP — Nexus Asia CRE Intel v4.0
========================================
Replaces spaCy + keyword matching with Gemini Flash.
Free tier: 1M tokens/day, 15 req/min.

What it does better than spaCy:
- Extracts exact sqft figures ("2.1 lakh sqft" → 210000)
- Identifies correct company even in messy headlines
- Detects urgency from context ("by Q3" → HIGH)
- Understands India-specific CRE language (GCC, SEZ, IT Park)
- Generates proper "why CRE" reasoning
- Works across 18 languages/markets
"""

import os
import json
import time
import re
import requests
from typing import Optional

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyCk_J6g8rovloY0N9PtnNUaJoon4nIYjDQ")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"

# Rate limiting — free tier is 15 req/min
_last_call = 0
_calls_this_minute = 0
_minute_start = 0

SYSTEM_PROMPT = """You are a Commercial Real Estate (CRE) intelligence analyst for Nexus Asia.
Your job: extract structured CRE demand signals from news articles.

India is the PRIMARY market. Be extra detailed for India signals.
For global signals, still extract accurately but India signals get priority.

You MUST respond with ONLY valid JSON. No explanation, no markdown, no backticks.
"""

EXTRACT_PROMPT = """Analyze this article for CRE demand signals:

ARTICLE: {text}

Extract and return ONLY this JSON (no other text):
{{
  "is_cre_relevant": true/false,
  "company_name": "exact company name or null",
  "signal_type": "OFFICE|LEASE|EXPAND|FUNDING|HIRING|WAREHOUSE|DATA CENTRE|RELOCATE|DISTRESS|FILING",
  "location": "specific city/area or null",
  "country": "country name",
  "region": "India|USA|UK|Singapore|UAE|Japan|Australia|China_HK|Korea|SEA|Germany|Canada|Global|India_Impact",
  "sqft": "number only if mentioned, else null",
  "summary": "one clear sentence under 120 chars describing the CRE event",
  "why_cre": "one sentence: why this matters for CRE brokers/landlords, under 80 chars",
  "confidence": 0-100,
  "urgency": "LOW|MEDIUM|HIGH|CRITICAL",
  "urgency_reason": "brief reason for urgency level"
}}

Rules:
- company_name: the TENANT/OCCUPIER company, not landlord/developer/news outlet
- signal_type: pick the STRONGEST signal (LEASE > OFFICE > EXPAND > others)
- confidence: 90+ only if sqft + company + location all confirmed. 70-89 if 2 of 3. Below 70 if vague.
- urgency HIGH if: timeline mentioned (Q1/Q2/by date), large sqft (>50k sqft), senior leadership move
- urgency CRITICAL if: NCLT/IBC/distress/immediate lease expiry
- India_Impact region: foreign company expanding INTO India
- If not CRE relevant, return {{"is_cre_relevant": false}}
"""

CHAT_PROMPT = """You are the Nexus Asia CRE Intelligence Assistant — an expert on commercial real estate across India and global markets.

You have access to live CRE signal data. Answer questions about:
- CRE market trends in India (Mumbai, Bengaluru, Hyderabad, Pune, Delhi NCR etc.)
- Global CRE markets (Singapore, Dubai, London, NYC etc.)
- Company expansion/leasing activity
- GCC/captive centre trends in India
- Demand signals, lead scoring, market intelligence
- How to interpret signals in the Nexus terminal

Be concise, data-driven, and speak like a senior CRE analyst.
If asked about specific companies or deals, say you can only show what's in the live feed.

Current signals context:
{signals_context}

User question: {question}
"""


def _rate_limit():
    """Respect Gemini free tier: 15 req/min."""
    global _last_call, _calls_this_minute, _minute_start
    now = time.time()
    if now - _minute_start > 60:
        _minute_start = now
        _calls_this_minute = 0
    if _calls_this_minute >= 14:
        sleep_time = 60 - (now - _minute_start) + 1
        print(f"[Gemini] Rate limit — sleeping {sleep_time:.1f}s")
        time.sleep(sleep_time)
        _minute_start = time.time()
        _calls_this_minute = 0
    # Min 100ms between calls
    elapsed = now - _last_call
    if elapsed < 0.1:
        time.sleep(0.1 - elapsed)
    _last_call = time.time()
    _calls_this_minute += 1


def _call_gemini(prompt: str, temperature: float = 0.1) -> Optional[str]:
    """Single Gemini API call. Returns text or None."""
    _rate_limit()
    try:
        resp = requests.post(
            GEMINI_URL,
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": 512,
                    "responseMimeType": "application/json",
                },
                "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"[Gemini] API error: {e}")
        return None


def gemini_extract_signal(title: str, text: str) -> Optional[dict]:
    """
    Extract structured CRE signal from article using Gemini.
    Returns dict or None if not CRE relevant.
    """
    combined = f"{title}\n\n{text[:1200]}"  # Cap at 1200 chars to save tokens
    prompt = EXTRACT_PROMPT.format(text=combined)
    
    raw = _call_gemini(prompt)
    if not raw:
        return None

    try:
        # Clean any accidental markdown
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"```json?\n?", "", raw).replace("```", "").strip()
        
        result = json.loads(raw)
        
        if not result.get("is_cre_relevant", False):
            return None

        # Validate required fields
        if not result.get("company_name"):
            return None

        return result

    except (json.JSONDecodeError, KeyError) as e:
        print(f"[Gemini] Parse error: {e} | raw: {raw[:100]}")
        return None


def gemini_chat(question: str, signals: list) -> str:
    """
    Answer a CRE question using Gemini with signals as context.
    Used by the frontend chatbox.
    """
    # Build compact context from top 20 signals
    context_lines = []
    for s in signals[:20]:
        co = s.get("companies", {}) or {}
        name = co.get("company_name", "Unknown") if isinstance(co, dict) else "Unknown"
        line = f"- {s.get('signal_type','?')} | {name} | {s.get('location','?')} | {s.get('country','?')} | conf:{s.get('confidence_score',0)}"
        context_lines.append(line)
    
    context = "\n".join(context_lines) if context_lines else "No signals loaded."
    prompt = CHAT_PROMPT.format(signals_context=context, question=question)
    
    try:
        _rate_limit()
        resp = requests.post(
            GEMINI_URL,
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.4,
                    "maxOutputTokens": 800,
                },
            },
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"Intelligence feed temporarily unavailable. Error: {str(e)[:80]}"


def batch_extract_signals(articles: list, fallback_fn=None) -> list:
    """
    Run Gemini extraction on a batch of articles.
    Falls back to existing NLP if Gemini fails.
    Returns list of (article, gemini_result) tuples where result is not None.
    """
    results = []
    total = len(articles)
    
    for i, article in enumerate(articles):
        title = article.get("title", "")
        text  = article.get("text", "")
        
        if not title and not text:
            continue

        print(f"[Gemini] {i+1}/{total} — {title[:50]}")
        
        result = gemini_extract_signal(title, text)
        
        if result:
            results.append((article, result))
        elif fallback_fn:
            # Fall back to spaCy-based extraction
            fallback = fallback_fn(article)
            if fallback:
                results.append((article, fallback))
    
    print(f"[Gemini] Extracted {len(results)}/{total} CRE signals")
    return results
