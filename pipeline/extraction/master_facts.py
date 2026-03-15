"""
NewsGT — Master Fact Set Builder
Aggregates all article_extractions for a story into a single master_fact_set.
Runs claim intersection + confidence weighting.
Stores result in stories.master_fact_set and populates claims table.
"""

import os
import json
import time
from dotenv import load_dotenv
from supabase import create_client
from groq import Groq

load_dotenv()
sb     = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

GROQ_MODEL    = "llama-3.3-70b-versatile"
REQUEST_DELAY = 1.0

# ── Domain agenda poles per category ─────────────────────────────────────────
AGENDA_POLES = {
    "Middle East & Gulf": [
        "Western mainstream",
        "Israeli",
        "Arab state",
        "Iranian",
        "Russian state",
        "Independent",
    ],
    "US Politics & Foreign Policy": [
        "US liberal establishment",
        "US conservative",
        "Adversarial left",
        "Russian state",
        "Chinese state",
        "Non-Western",
    ],
    "Russia / Ukraine / NATO": [
        "Russian state",
        "Western mainstream",
        "European",
        "Ukrainian",
        "Global South",
    ],
    "China / Taiwan / Indo-Pacific": [
        "CCP",
        "HK-adjacent",
        "Japanese",
        "ASEAN",
        "Western financial",
    ],
    "Global Economy & Trade Wars": [
        "Financial West",
        "US conservative",
        "Japanese",
        "Chinese state",
        "Latin American",
    ],
    "South Asia": [
        "Indian nationalist",
        "Indian progressive",
        "Pakistani",
        "Independent Indian",
    ],
    "Africa & Resources": [
        "African independent",
        "French state",
        "Chinese state",
        "Western wire",
    ],
    "Technology & AI Power": [
        "Financial West",
        "Chinese state",
        "Japanese",
        "US conservative",
        "Liberal internationalist",
    ],
    "Climate & Energy Transition": [
        "Progressive",
        "Financial",
        "French state",
        "Qatari",
        "Russian state",
        "Latin American",
    ],
}

# Source → agenda pole mapping per category
SOURCE_POLES = {
    "Middle East & Gulf": {
        "Reuters":                  "Western mainstream",
        "Associated Press":         "Western mainstream",
        "AFP":                      "Western mainstream",
        "BBC":                      "Western mainstream",
        "New York Times":           "Western mainstream",
        "Financial Times":          "Western mainstream",
        "The Economist":            "Western mainstream",
        "Bloomberg":                "Western mainstream",
        "NPR":                      "Western mainstream",
        "PBS":                      "Western mainstream",
        "Axios":                    "Western mainstream",
        "Christian Science Monitor":"Western mainstream",
        "Al Jazeera":               "Arab state",
        "Arab News":                "Arab state",
        "Middle East Eye":          "Independent",
        "Haaretz":                  "Israeli",
        "Jerusalem Post":           "Israeli",
        "Times of Israel":          "Israeli",
        "RT":                       "Russian state",
        "TASS":                     "Russian state",
        "Press TV":                 "Iranian",
        "Dawn":                     "Independent",
        "The Hindu":                "Independent",
        "Times of India":           "Independent",
    },
    "Russia / Ukraine / NATO": {
        "Reuters":          "Western mainstream",
        "Associated Press": "Western mainstream",
        "AFP":              "Western mainstream",
        "BBC":              "Western mainstream",
        "New York Times":   "Western mainstream",
        "Financial Times":  "Western mainstream",
        "The Economist":    "Western mainstream",
        "Euractiv":         "European",
        "DW":               "European",
        "Der Spiegel":      "European",
        "Kyiv Independent": "Ukrainian",
        "Meduza":           "Ukrainian",
        "RT":               "Russian state",
        "TASS":             "Russian state",
        "Al Jazeera":       "Global South",
        "Times of India":   "Global South",
        "The Hindu":        "Global South",
    },
    "China / Taiwan / Indo-Pacific": {
        "Reuters":                  "Western financial",
        "Financial Times":          "Western financial",
        "Bloomberg":                "Western financial",
        "The Economist":            "Western financial",
        "Nikkei":                   "Japanese",
        "Asia Times":               "ASEAN",
        "Straits Times":            "ASEAN",
        "The Diplomat":             "ASEAN",
        "CGTN":                     "CCP",
        "South China Morning Post": "HK-adjacent",
    },
    "US Politics & Foreign Policy": {
        "New York Times":           "US liberal establishment",
        "NPR":                      "US liberal establishment",
        "PBS":                      "US liberal establishment",
        "Axios":                    "US liberal establishment",
        "Christian Science Monitor":"US liberal establishment",
        "Wall Street Journal":      "US conservative",
        "The Intercept":            "Adversarial left",
        "Foreign Policy":           "US liberal establishment",
        "RT":                       "Russian state",
        "CGTN":                     "Chinese state",
        "Al Jazeera":               "Non-Western",
        "Times of India":           "Non-Western",
        "The Hindu":                "Non-Western",
        "Dawn":                     "Non-Western",
    },
    "Global Economy & Trade Wars": {
        "Bloomberg":        "Financial West",
        "Financial Times":  "Financial West",
        "The Economist":    "Financial West",
        "Reuters":          "Financial West",
        "Wall Street Journal": "US conservative",
        "Nikkei":           "Japanese",
        "CGTN":             "Chinese state",
        "Folha de S.Paulo": "Latin American",
    },
    "South Asia": {
        "Times of India":   "Indian nationalist",
        "The Hindu":        "Indian progressive",
        "The Wire India":   "Indian progressive",
        "Dawn":             "Pakistani",
        "Reuters":          "Western wire",
        "AFP":              "Western wire",
    },
    "Africa & Resources": {
        "Daily Maverick":   "African independent",
        "AllAfrica":        "African independent",
        "Africa Check":     "African independent",
        "France 24":        "French state",
        "AFP":              "French state",
        "CGTN":             "Chinese state",
        "Reuters":          "Western wire",
        "AP":               "Western wire",
    },
    "Technology & AI Power": {
        "Bloomberg":                "Financial West",
        "Financial Times":          "Financial West",
        "The Economist":            "Financial West",
        "Wired":                    "Liberal internationalist",
        "Ars Technica":             "Liberal internationalist",
        "MIT Technology Review":    "Liberal internationalist",
        "CGTN":                     "Chinese state",
        "Nikkei":                   "Japanese",
        "Wall Street Journal":      "US conservative",
    },
    "Climate & Energy Transition": {
        "Carbon Brief":     "Progressive",
        "Climate Central":  "Progressive",
        "The Guardian":     "Progressive",
        "Bloomberg":        "Financial",
        "Financial Times":  "Financial",
        "France 24":        "French state",
        "Al Jazeera":       "Qatari",
        "RT":               "Russian state",
        "Folha de S.Paulo": "Latin American",
    },
}


# ── Confidence weighting ──────────────────────────────────────────────────────
def confidence_score(sources: list[dict], category: str) -> tuple[float, str]:
    """
    Calculate confidence score for a claim.
    confidence = Σ(credibility_weight) × D
    D = distinct poles / total poles in category
    Returns (score, label).
    """
    poles_map    = SOURCE_POLES.get(category, {})
    total_poles  = len(AGENDA_POLES.get(category, []))
    if total_poles == 0:
        total_poles = 1

    cred_sum     = sum(s.get("credibility_weight", 0.4) for s in sources)
    poles_seen   = set(poles_map.get(s.get("name", ""), "Unknown") for s in sources)
    D            = len(poles_seen) / total_poles

    score = min(cred_sum * D, 1.0)  # cap at 1.0

    if score >= 0.8:
        label = "ESTABLISHED"
    elif score >= 0.5:
        label = "PROBABLE"
    elif score >= 0.3:
        label = "ASSESSED"
    else:
        label = "SPECULATIVE"

    return round(score, 3), label


# ── LLM claim intersection ────────────────────────────────────────────────────
INTERSECTION_PROMPT = """You are a fact aggregation engine.

Given multiple 5W1H extractions from different news sources covering the same event,
your task is to:
1. Identify the INTERSECTION — factual claims that appear across multiple sources
2. Identify DIVERGENCES — where sources differ significantly in framing or facts

RULES:
- Only include claims explicitly stated in the sources
- Use neutral language — strip all emotional framing
- Each claim must be a single, verifiable factual statement
- Note which sources support each claim

Return ONLY valid JSON:
{
  "verified_sequence": [
    "string — neutral chronological event statement"
  ],
  "key_claims": [
    {
      "claim": "string — single verifiable fact",
      "sources": ["source name 1", "source name 2"]
    }
  ],
  "divergences": [
    {
      "topic": "string — what the sources disagree on",
      "versions": {
        "source name": "what they say"
      }
    }
  ],
  "actors": [
    {
      "name": "string",
      "type": "person|organization|state|group",
      "role": "string"
    }
  ]
}"""


def build_intersection(extractions: list[dict], category: str) -> dict | None:
    """Use LLM to find claim intersection across all extractions."""

    # Format extractions for the prompt
    formatted = []
    for e in extractions:
        source = e.get("source_name", "Unknown")
        formatted.append(f"""
SOURCE: {source}
WHAT: {e.get('what', 'N/A')}
WHEN: {e.get('when_text', 'N/A')}
WHERE: {e.get('where_text', 'N/A')}
WHY: {e.get('why', 'N/A')}
HOW: {e.get('how', 'N/A')}
KEY CLAIMS: {json.dumps(e.get('raw_extraction', {}).get('key_claims', []))}
""")

    prompt = f"""Find the factual intersection across these {len(extractions)} source extractions:

{'---'.join(formatted)}

Return only valid JSON as specified."""

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": INTERSECTION_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.0,
            max_tokens=4000,
        )

        raw = response.choices[0].message.content.strip()

        # Strip markdown fences
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
            return None
        return json.loads(raw[start:end])

    except Exception as e:
        print(f"  ⚠️  Intersection LLM error: {e}")
        return None


# ── Main builder ──────────────────────────────────────────────────────────────
def build_master_facts(story_id: str) -> dict:
    """
    Build master fact set for a story:
    1. Load all extractions + source metadata
    2. Run LLM intersection
    3. Score each claim with confidence weighting
    4. Store master_fact_set in stories table
    5. Populate claims table
    """
    # Load story
    story_result = (
        sb.table("stories")
        .select("id, category_label, master_version")
        .eq("id", story_id)
        .execute()
    )
    if not story_result.data:
        print(f"  Story not found: {story_id}")
        return {}

    story        = story_result.data[0]
    category     = story["category_label"]
    master_ver   = story["master_version"]

    # Load extractions with source metadata
    extractions_result = (
        sb.table("article_extractions")
        .select("*, source_profiles(name, credibility_weight)")
        .eq("story_id", story_id)
        .execute()
    )

    if not extractions_result.data:
        print(f"  No extractions for story {story_id[:8]}...")
        return {}

    extractions = extractions_result.data
    print(f"  {len(extractions)} extractions loaded for story {story_id[:8]}...")

    # Enrich extractions with source name
    for e in extractions:
        profile = e.get("source_profiles", {}) or {}
        e["source_name"]        = profile.get("name", "Unknown")
        e["credibility_weight"] = profile.get("credibility_weight", 0.4)

    # Run LLM intersection
    print(f"  Running claim intersection...")
    intersection = build_intersection(extractions, category)
    if not intersection:
        print(f"  ⚠️  Intersection failed")
        return {}

    time.sleep(REQUEST_DELAY)

    # Build source lookup for confidence scoring
    source_meta = [
        {"name": e["source_name"], "credibility_weight": e["credibility_weight"]}
        for e in extractions
    ]

    # Score and store claims
    claims_stored = 0
    for claim_data in intersection.get("key_claims", []):
        claim_text      = claim_data.get("claim", "")
        claim_sources   = claim_data.get("sources", [])

        if not claim_text:
            continue

        # Get metadata for sources that support this claim
        supporting = [s for s in source_meta if s["name"] in claim_sources]
        if not supporting:
            supporting = source_meta  # fallback: all sources

        score, label = confidence_score(supporting, category)

        # Build agenda positions for supporting sources
        poles_map  = SOURCE_POLES.get(category, {})
        agenda_pos = {s["name"]: poles_map.get(s["name"], "Unknown") for s in supporting}
        poles_covered = list(set(agenda_pos.values()))

        sb.table("claims").insert({
            "story_id":               story_id,
            "claim_text":             claim_text,
            "sources_reporting":      claim_sources,
            "source_agenda_positions":agenda_pos,
            "confidence_score":       score,
            "confidence_label":       label,
            "agenda_poles_covered":   poles_covered,
        }).execute()
        claims_stored += 1

    # Store master_fact_set in stories table
    master_fact_set = {
        "verified_sequence": intersection.get("verified_sequence", []),
        "divergences":       intersection.get("divergences", []),
        "actors":            intersection.get("actors", []),
        "sources_count":     len(extractions),
        "claims_count":      claims_stored,
    }

    sb.table("stories").update({
        "master_fact_set": master_fact_set,
        "master_version":  master_ver + 1,
    }).eq("id", story_id).execute()

    print(f"  ✅ Master fact set built: {claims_stored} claims stored")
    print(f"\n  Verified sequence:")
    for event in intersection.get("verified_sequence", []):
        print(f"    • {event}")

    print(f"\n  Divergences:")
    for div in intersection.get("divergences", []):
        print(f"    Topic: {div.get('topic', '')}")
        for src, version in div.get("versions", {}).items():
            print(f"      [{src}] {version}")

    return master_fact_set


def build_all() -> None:
    """Build master fact sets for all stories."""
    stories = sb.table("stories").select("id, headline").execute()
    for story in stories.data:
        headline = (story.get("headline") or "")[:60]
        print(f"\n── {headline} ──")
        build_master_facts(story["id"])


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if len(sys.argv) == 2:
        build_master_facts(sys.argv[1])
    else:
        build_all()