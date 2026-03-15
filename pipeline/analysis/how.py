"""
NewsGT — HOW Layer
Analyzes operational mechanics per actor:
  - What levers they are pulling
  - What constraints they operate under (resources, alliances, domestic pressure)
  - Financial signals injected as grounding data
Stores result in layer_outputs table (layer = 'HOW').
"""

import os
import json
import time
import yfinance as yf
from fredapi import Fred
from dotenv import load_dotenv
from supabase import create_client
from groq import Groq

load_dotenv()
sb     = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
fred   = Fred(api_key=os.getenv("FRED_API_KEY"))

GROQ_MODEL    = "llama-3.3-70b-versatile"
REQUEST_DELAY = 1.0

# ── Financial metric identification prompt ────────────────────────────────────
METRIC_ID_PROMPT = """You are a financial intelligence analyst.

Given a geopolitical story and its actors, identify the 5-8 most relevant
financial metrics that would reveal material interests and operational constraints.

For each metric specify:
- name: descriptive name
- description: what it measures
- api: one of "yfinance" or "fred"
- ticker_or_id: exact yfinance ticker or FRED series ID
- relevance: one sentence on why this matters for this story

IMPORTANT:
- Use only real, valid tickers and FRED series IDs
- yfinance: use standard tickers (BZ=F for Brent crude, DX-Y.NYB for USD index, etc.)
- FRED: use standard series IDs (DCOILBRENTEU for Brent, GOLDAMGBD228NLBM for gold, etc.)

Return ONLY valid JSON:
{
  "metrics": [
    {
      "name": "string",
      "description": "string",
      "api": "yfinance|fred",
      "ticker_or_id": "string",
      "relevance": "string"
    }
  ]
}"""

# ── HOW analysis prompt ───────────────────────────────────────────────────────
HOW_PROMPT = """You are a geopolitical operational analysis engine.

You will be given:
1. Verified event sequence
2. Actor map (from WHO layer)
3. Live financial data relevant to this story
4. Verified claims with confidence labels

Your task: analyze the OPERATIONAL MECHANICS per actor.

For each actor explain:
- LEVERS: what specific tools/capabilities they are deploying
- CONSTRAINTS: what limits their options (resources, alliances, domestic politics, geography)
- FINANCIAL DIMENSION: what the financial data reveals about their material position

RULES:
- Ground every claim in the verified facts or financial data provided
- No speculation beyond what evidence supports
- Label each claim: ESTABLISHED | PROBABLE | ASSESSED | SPECULATIVE

Return ONLY valid JSON:
{
  "actor_mechanics": [
    {
      "actor": "string",
      "levers": [
        {
          "lever": "string — specific capability being deployed",
          "evidence": "string — what supports this",
          "confidence": "ESTABLISHED|PROBABLE|ASSESSED|SPECULATIVE"
        }
      ],
      "constraints": [
        {
          "constraint": "string — specific limiting factor",
          "evidence": "string",
          "confidence": "ESTABLISHED|PROBABLE|ASSESSED|SPECULATIVE"
        }
      ],
      "financial_dimension": "string — what financial data reveals about this actor"
    }
  ],
  "operational_summary": "string — 2-3 sentences on the overall operational dynamic"
}"""


# ── Financial data fetcher ────────────────────────────────────────────────────
def identify_metrics(story_context: str, actors: list[str]) -> list[dict]:
    """Use LLM to identify relevant financial metrics for this story."""
    prompt = f"""STORY CONTEXT: {story_context}
ACTORS: {', '.join(actors)}

Identify the 5-8 most relevant financial metrics. Return only valid JSON."""

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": METRIC_ID_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.0,
            max_tokens=1500,
        )
        raw = response.choices[0].message.content.strip()
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start == -1:
            return []
        data = json.loads(raw[start:end])
        return data.get("metrics", [])
    except Exception as e:
        print(f"  ⚠️  Metric identification error: {e}")
        return []


def fetch_metric(metric: dict) -> dict:
    """Fetch a single financial metric value."""
    api    = metric.get("api", "")
    ticker = metric.get("ticker_or_id", "")
    result = {**metric, "value": None, "unit": "", "available": False}

    try:
        if api == "yfinance":
            t    = yf.Ticker(ticker)
            hist = t.history(period="5d")
            if not hist.empty:
                result["value"]     = round(float(hist["Close"].iloc[-1]), 2)
                result["unit"]      = "USD"
                result["available"] = True

        elif api == "fred":
            series = fred.get_series(ticker, limit=1)
            if not series.empty:
                result["value"]     = round(float(series.iloc[-1]), 4)
                result["unit"]      = ""
                result["available"] = True

    except Exception as e:
        print(f"    ⚠️  Failed to fetch {ticker}: {e}")

    return result


def fetch_financial_data(story_id: str, story_context: str,
                         actors: list[str]) -> list[dict]:
    """Identify and fetch all relevant financial metrics for a story."""
    print(f"  Identifying financial metrics...")
    metrics = identify_metrics(story_context, actors)
    time.sleep(REQUEST_DELAY)

    if not metrics:
        print(f"  ⚠️  No metrics identified")
        return []

    print(f"  Fetching {len(metrics)} metrics...")
    fetched = []
    for m in metrics:
        result = fetch_metric(m)
        status = "✅" if result["available"] else "❌"
        val    = f"{result['value']} {result['unit']}" if result["available"] else "unavailable"
        print(f"    {status} {m.get('name','')}: {val}")

        # Normalise api_source to match DB check constraint
        api_raw = m.get("api", "yfinance").lower().strip()
        api_map = {"yfinance": "yfinance", "fred": "FRED",
                   "worldbank": "WorldBank", "imf": "IMF",
                   "alphaadvantage": "AlphaVantage"}
        api_source = api_map.get(api_raw, "yfinance")

        sb.table("financial_snapshots").insert({
            "story_id":           story_id,
            "metric_name":        m.get("name", ""),
            "metric_description": m.get("description", ""),
            "api_source":         api_source,
            "ticker_or_series_id":m.get("ticker_or_id", ""),
            "value":              result.get("value"),
            "unit":               result.get("unit", ""),
            "relevance_note":     m.get("relevance", ""),
            "available":          result["available"],
        }).execute()

        fetched.append(result)

    return fetched


# ── HOW layer builder ─────────────────────────────────────────────────────────
def build_how(story_id: str) -> dict:
    """Build HOW layer for a story."""

    # Load story + WHO output
    story_result = (
        sb.table("stories")
        .select("id, category_label, master_fact_set, headline")
        .eq("id", story_id)
        .execute()
    )
    if not story_result.data:
        print(f"  Story not found: {story_id}")
        return {}

    story     = story_result.data[0]
    category  = story["category_label"]
    master_fs = story.get("master_fact_set") or {}
    headline  = (story.get("headline") or "")[:60]

    print(f"\n── HOW: {headline} ──")

    # Load WHO layer output
    who_result = (
        sb.table("layer_outputs")
        .select("content")
        .eq("story_id", story_id)
        .eq("layer", "WHO")
        .execute()
    )
    if not who_result.data:
        print(f"  WHO layer not found — run who.py first")
        return {}

    who_content = who_result.data[0]["content"]
    actors      = [a["name"] for a in who_content.get("actors", [])]

    # Load claims
    claims_result = (
        sb.table("claims")
        .select("claim_text, confidence_label, sources_reporting")
        .eq("story_id", story_id)
        .execute()
    )
    claims = claims_result.data or []

    # Build story context for metric identification
    story_context = " ".join(master_fs.get("verified_sequence", []))

    # Fetch financial data
    financial_data = fetch_financial_data(story_id, story_context, actors)
    time.sleep(REQUEST_DELAY)

    # Format financial snapshot for prompt
    fin_summary = []
    for m in financial_data:
        if m["available"]:
            fin_summary.append(
                f"{m['name']}: {m['value']} {m.get('unit','')} — {m.get('relevance','')}"
            )
        else:
            fin_summary.append(f"{m['name']}: DATA UNAVAILABLE — {m.get('relevance','')}")

    # Build HOW prompt
    prompt = f"""VERIFIED EVENT SEQUENCE:
{json.dumps(master_fs.get('verified_sequence', []), indent=2)}

ACTOR MAP:
{json.dumps(who_content.get('actors', []), indent=2)}

FINANCIAL DATA:
{chr(10).join(fin_summary) if fin_summary else 'No financial data available'}

VERIFIED CLAIMS:
{json.dumps([{'claim': c['claim_text'], 'confidence': c['confidence_label']} for c in claims[:10]], indent=2)}

CATEGORY: {category}

Analyze operational mechanics per actor. Return only valid JSON."""

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": HOW_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.0,
            max_tokens=4000,
        )

        raw = response.choices[0].message.content.strip()

        if "```" in raw:
            parts = raw.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    raw = part
                    break

        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start == -1 or end == 0:
            print("  ⚠️  No JSON in HOW response")
            return {}

        result = json.loads(raw[start:end])

    except Exception as e:
        print(f"  ⚠️  HOW LLM error: {e}")
        return {}

    # Determine overall confidence
    all_confidences = []
    for actor_mech in result.get("actor_mechanics", []):
        for lever in actor_mech.get("levers", []):
            all_confidences.append(lever.get("confidence", "ASSESSED"))
        for constraint in actor_mech.get("constraints", []):
            all_confidences.append(constraint.get("confidence", "ASSESSED"))

    conf_order   = ["ESTABLISHED", "PROBABLE", "ASSESSED", "SPECULATIVE"]
    overall_conf = "ASSESSED"
    if all_confidences:
        counts = {c: all_confidences.count(c) for c in conf_order}
        overall_conf = max(counts, key=counts.get)

    # Store in layer_outputs
    sb.table("layer_outputs").insert({
        "story_id":          story_id,
        "layer":             "HOW",
        "content":           result,
        "confidence_overall":overall_conf,
        "model_used":        GROQ_MODEL,
    }).execute()

    # Print output
    print(f"\n  Operational Summary:")
    print(f"  {result.get('operational_summary', '')}")
    print()

    for mech in result.get("actor_mechanics", []):
        print(f"  [{mech.get('actor','')}]")
        for lever in mech.get("levers", [])[:2]:
            print(f"    LEVER [{lever.get('confidence','?')}]: {lever.get('lever','')[:80]}")
        for constraint in mech.get("constraints", [])[:2]:
            print(f"    CONSTRAINT [{constraint.get('confidence','?')}]: {constraint.get('constraint','')[:80]}")
        fin = mech.get("financial_dimension", "")
        if fin:
            print(f"    FINANCIAL: {fin[:100]}")
        print()

    return result


def build_all_how() -> None:
    stories = sb.table("stories").select("id, headline").execute()
    for story in stories.data:
        build_how(story["id"])
        time.sleep(REQUEST_DELAY)


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if len(sys.argv) == 2:
        build_how(sys.argv[1])
    else:
        build_all_how()