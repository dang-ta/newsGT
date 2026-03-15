"""
NewsGT — Bias Analyzer
Computes the 5 behavioral signals for each source on a given story:
  1. Selection    — did they cover it? how prominently?
  2. Framing      — agent/patient/verb role assignment per actor
  3. Omission     — what's in master fact set but missing here
  4. Language     — word choice, emotional loading, labels
  5. Sourcing     — whose voices are quoted, which sides represented

Stores results in behavioral_records table.
Compares against manual bias profiles (historical prior).
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

# ── Bias analysis prompt ──────────────────────────────────────────────────────
BIAS_PROMPT = """You are a media bias analysis engine.

You will be given:
1. A MASTER FACT SET — the verified facts agreed upon across multiple sources
2. A SINGLE ARTICLE — from one specific source

Your task is to analyze this article across 5 behavioral signals:

SIGNAL 1 — SELECTION
How prominently does this source cover this story?
Score: 1.0 (lead story, extensive) | 0.7 (covered well) | 0.4 (brief mention) | 0.1 (barely covered)

SIGNAL 2 — FRAMING
For each actor in the story, how does this source position them?
- agent: actively doing something (aggressor, decision-maker)
- patient: receiving action (victim, target)
- neutral: mentioned without clear role assignment
Also note the key verb used to describe their action.

SIGNAL 3 — OMISSION
Which facts from the master fact set are ABSENT from this article?
List each missing fact explicitly.

SIGNAL 4 — LANGUAGE
Identify loaded language, emotional framing, and label choices.
Examples: "strike" vs "attack" vs "bombing", "militants" vs "terrorists" vs "fighters"
Note any language that reveals editorial positioning.

SIGNAL 5 — SOURCING
Whose voices are quoted or cited?
Which sides of the conflict are represented?
Which sides are absent?

RULES:
- Be specific and evidence-based. Quote the article text.
- No inference beyond what's in the text.
- Neutral analytical tone throughout.

Return ONLY valid JSON:
{
  "selection_score": float (0.0-1.0),
  "framing": {
    "actors": [
      {
        "name": "string",
        "role": "agent|patient|neutral",
        "verb": "string — key action verb used",
        "framing_note": "string — how this source positions them"
      }
    ]
  },
  "omission": {
    "missing_facts": ["string — fact from master set absent here"],
    "omission_notes": "string — pattern or significance of omissions"
  },
  "language": {
    "loaded_terms": [
      {
        "term": "string — word used",
        "alternative": "string — neutral alternative",
        "significance": "string — what this choice reveals"
      }
    ],
    "overall_tone": "string — brief characterization of emotional register"
  },
  "sourcing": {
    "voices_quoted": ["string — name or title of quoted source"],
    "sides_represented": ["string"],
    "sides_absent": ["string"],
    "sourcing_notes": "string"
  }
}"""


# ── Per-source analysis ───────────────────────────────────────────────────────
def analyze_source(article_text: str, master_fact_set: dict,
                   source_name: str) -> dict | None:
    """Run 5-signal bias analysis for one source against master fact set."""

    master_summary = json.dumps({
        "verified_sequence": master_fact_set.get("verified_sequence", []),
        "key_actors":        [a["name"] for a in master_fact_set.get("actors", [])],
    }, indent=2)

    prompt = f"""MASTER FACT SET:
{master_summary}

SOURCE: {source_name}
ARTICLE TEXT:
{article_text[:3000]}

Analyze this article's bias across the 5 signals. Return only valid JSON."""

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": BIAS_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.0,
            max_tokens=3000,
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
        print(f"    ⚠️  Bias analysis error for {source_name}: {e}")
        return None


def check_divergence(result: dict, source_name: str,
                     manual_profile: dict, category: str) -> tuple[bool, str]:
    """
    Compare current behavior against manual bias profile prior.
    Returns (divergence_flag, divergence_detail).
    """
    prior = manual_profile.get(category, {})
    prior_notes = prior.get("notes", "")

    if not prior_notes or prior.get("status") == "placeholder":
        return False, "No prior established — placeholder profile"

    # Simple heuristic: check if omission pattern or framing
    # is significantly different from prior description
    # Phase 2: replace with statistical comparison against behavioral_records
    missing = result.get("omission", {}).get("missing_facts", [])
    if len(missing) >= 3:
        return True, f"High omission count ({len(missing)} facts missing from master set)"

    return False, ""


# ── Story-level batch analysis ────────────────────────────────────────────────
def analyze_story(story_id: str) -> dict:
    """
    Run bias analysis for all articles in a story.
    Stores results in behavioral_records.
    """
    # Load story
    story_result = (
        sb.table("stories")
        .select("id, category_label, master_fact_set, master_version, headline")
        .eq("id", story_id)
        .execute()
    )
    if not story_result.data:
        print(f"  Story not found: {story_id}")
        return {}

    story          = story_result.data[0]
    category       = story["category_label"]
    master_ver     = story["master_version"]
    master_fs      = story.get("master_fact_set") or {}
    headline       = (story.get("headline") or "")[:60]

    if not master_fs.get("verified_sequence"):
        print(f"  No master fact set — run master_facts.py first")
        return {}

    print(f"\n── Bias analysis: {headline} ──")
    print(f"  Category: {category}")

    # Load articles with source metadata
    articles_result = (
        sb.table("articles")
        .select("id, story_id, source_id, raw_text, source_profiles(id, name, credibility_weight, manual_bias_profiles)")
        .eq("story_id", story_id)
        .eq("processed", True)
        .execute()
    )

    if not articles_result.data:
        print(f"  No articles found")
        return {}

    analyzed, failed, skipped = 0, 0, 0

    for article in articles_result.data:
        raw_text = article.get("raw_text", "")
        profile  = article.get("source_profiles", {}) or {}
        source_name     = profile.get("name", "Unknown")
        source_id       = article.get("source_id")
        manual_profiles = profile.get("manual_bias_profiles") or {}

        if not raw_text or len(raw_text.strip()) < 100:
            print(f"  ⏭  Skipping {source_name} (no content)")
            skipped += 1
            continue

        # Skip if already analyzed for this story+source+version
        existing = (
            sb.table("behavioral_records")
            .select("id")
            .eq("story_id", story_id)
            .eq("source_id", source_id)
            .eq("master_version", master_ver)
            .execute()
        )
        if existing.data:
            print(f"  ⏭  Skipping {source_name} (already analyzed)")
            skipped += 1
            continue

        print(f"  Analyzing: [{source_name}]...")
        result = analyze_source(raw_text, master_fs, source_name)

        if not result:
            failed += 1
            continue

        # Check divergence against prior
        diverge_flag, diverge_detail = check_divergence(
            result, source_name, manual_profiles, category
        )

        # Build behavioral record
        record = {
            "source_id":        source_id,
            "story_id":         story_id,
            "category_label":   category,
            "master_version":   master_ver,
            "selection_score":  result.get("selection_score", 0.5),
            "framing_scores":   result.get("framing", {}),
            "omission_profile": result.get("omission", {}),
            "language_tone":    result.get("language", {}),
            "sourcing_profile": result.get("sourcing", {}),
            "divergence_flag":  diverge_flag,
            "divergence_detail":diverge_detail,
        }

        sb.table("behavioral_records").insert(record).execute()

        # Print summary
        missing = result.get("omission", {}).get("missing_facts", [])
        framing = result.get("framing", {}).get("actors", [])
        tone    = result.get("language", {}).get("overall_tone", "")

        print(f"    Selection: {result.get('selection_score', 0):.1f} | "
              f"Omissions: {len(missing)} | "
              f"Tone: {tone[:60]}")

        for actor in framing[:3]:
            print(f"    [{actor.get('role','?').upper()}] {actor.get('name','')} "
                  f"— {actor.get('verb','')} — {actor.get('framing_note','')[:60]}")

        if missing:
            print(f"    Missing facts:")
            for m in missing[:3]:
                print(f"      • {m[:80]}")

        if diverge_flag:
            print(f"    ⚠️  DIVERGENCE: {diverge_detail}")

        analyzed += 1
        time.sleep(REQUEST_DELAY)

    print(f"\n  Done: {analyzed} analyzed, {failed} failed, {skipped} skipped")
    return {"analyzed": analyzed, "failed": failed, "skipped": skipped}


def analyze_all() -> None:
    """Run bias analysis for all stories."""
    stories = sb.table("stories").select("id, headline").execute()
    for story in stories.data:
        analyze_story(story["id"])


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if len(sys.argv) == 2:
        analyze_story(sys.argv[1])
    else:
        analyze_all()