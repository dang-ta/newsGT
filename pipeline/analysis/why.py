"""
NewsGT — WHY Layer
Analyzes deep motivations per actor:
  - Structural forces (Turchin, Dalio, Ibn Khaldun)
  - Ideological scripts (actors' own published doctrines)
  - Material interests (follow the money, follow the power)
Confidence labeling on every claim.
Stores result in layer_outputs (layer = 'WHY').
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

# ── WHY prompt ────────────────────────────────────────────────────────────────
WHY_PROMPT = """You are a geopolitical deep motivation analysis engine.

You will be given:
1. Verified event sequence
2. Actor map (WHO layer)
3. Operational mechanics (HOW layer)
4. Financial data (with availability flags)
5. Verified claims with confidence labels

Your task: analyze DEEP MOTIVATIONS per actor across three sub-lenses.

SUB-LENS 1 — STRUCTURAL FORCES
Apply Turchin (elite overproduction, state fragility, intra-elite competition),
Dalio (debt/empire cycles, reserve currency dynamics), and
Ibn Khaldun (asabiyyah — social cohesion, group solidarity) frameworks.
What structural pressures are driving this actor's behavior?

SUB-LENS 2 — IDEOLOGICAL SCRIPTS
What documented ideology, doctrine, or strategic framework is this actor following?
Cite only publicly stated doctrines, published strategies, or official positions.
Examples: US neoconservative foreign policy doctrine, Israeli security doctrine,
Iranian revolutionary ideology, etc.
NO conspiracy inference — only what actors themselves have stated publicly.

SUB-LENS 3 — MATERIAL INTERESTS
Follow the money and the power.
What does this actor concretely gain or lose regardless of stated position?
Ground in financial data where available.

CONFIDENCE LABELING — apply to every analytical claim:
ESTABLISHED: documented, verifiable fact
PROBABLE: strongly supported by multiple evidence strands
ASSESSED: reasoned inference from available evidence
SPECULATIVE: plausible hypothesis, limited direct evidence

NOTE: Downgrade confidence when financial data is unavailable.

RULES:
- Every claim needs a confidence label
- Distinguish between empirically validated frameworks (PROBABLE/ESTABLISHED)
  and applied interpretations (ASSESSED/SPECULATIVE)
- No hidden actors, no conspiracy framing
- Ground ideological scripts in publicly available documents

Return ONLY valid JSON:
{
  "actor_motivations": [
    {
      "actor": "string",
      "structural_forces": {
        "analysis": "string",
        "turchin_signal": "string — elite overproduction / state fragility indicators",
        "dalio_signal": "string — empire/debt cycle position",
        "ibn_khaldun_signal": "string — asabiyyah level and direction",
        "confidence": "ESTABLISHED|PROBABLE|ASSESSED|SPECULATIVE"
      },
      "ideological_script": {
        "doctrine": "string — name of doctrine/framework",
        "description": "string — what this doctrine prescribes",
        "evidence": "string — publicly stated source",
        "how_it_applies": "string — how it explains this actor's behavior",
        "confidence": "ESTABLISHED|PROBABLE|ASSESSED|SPECULATIVE"
      },
      "material_interests": {
        "gains": ["string — concrete gain"],
        "losses": ["string — concrete loss/risk"],
        "financial_grounding": "string — what financial data supports this",
        "confidence": "ESTABLISHED|PROBABLE|ASSESSED|SPECULATIVE"
      }
    }
  ],
  "synthesis": "string — 3 sentences max. The working narrative that survives all three lenses.",
  "key_variable": "string — the single observable thing that confirms or breaks this analysis",
  "confidence_assessment": "string — overall confidence level and what would falsify it"
}"""


def build_why(story_id: str) -> dict:
    """Build WHY layer for a story."""

    # Load story
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

    print(f"\n── WHY: {headline} ──")

    # Load WHO layer
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

    # Load HOW layer
    how_result = (
        sb.table("layer_outputs")
        .select("content")
        .eq("story_id", story_id)
        .eq("layer", "HOW")
        .execute()
    )
    if not how_result.data:
        print(f"  HOW layer not found — run how.py first")
        return {}
    how_content = how_result.data[0]["content"]

    # Load financial snapshots
    fin_result = (
        sb.table("financial_snapshots")
        .select("metric_name, value, unit, relevance_note, available")
        .eq("story_id", story_id)
        .execute()
    )
    financial = fin_result.data or []

    # Load claims
    claims_result = (
        sb.table("claims")
        .select("claim_text, confidence_label")
        .eq("story_id", story_id)
        .execute()
    )
    claims = claims_result.data or []

    # Format financial summary
    fin_lines = []
    for f in financial:
        if f["available"] and f["value"] is not None:
            fin_lines.append(
                f"{f['metric_name']}: {f['value']} {f.get('unit','')} "
                f"[AVAILABLE] — {f.get('relevance_note','')}"
            )
        else:
            fin_lines.append(
                f"{f['metric_name']}: UNAVAILABLE — "
                f"{f.get('relevance_note','')} [confidence downgraded]"
            )

    prompt = f"""VERIFIED EVENT SEQUENCE:
{json.dumps(master_fs.get('verified_sequence', []), indent=2)}

ACTOR MAP (WHO):
{json.dumps(who_content.get('actors', []), indent=2)}

OPERATIONAL MECHANICS (HOW):
{json.dumps(how_content.get('actor_mechanics', []), indent=2)}

FINANCIAL DATA:
{chr(10).join(fin_lines) if fin_lines else 'No financial data available'}

VERIFIED CLAIMS:
{json.dumps([{'claim': c['claim_text'], 'confidence': c['confidence_label']} for c in claims], indent=2)}

CATEGORY: {category}

Analyze deep motivations. Return only valid JSON."""

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": WHY_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.0,
            max_tokens=5000,
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
            print("  ⚠️  No JSON in WHY response")
            return {}

        result = json.loads(raw[start:end])

    except Exception as e:
        print(f"  ⚠️  WHY LLM error: {e}")
        return {}

    # Overall confidence from actor motivations
    conf_labels = []
    for m in result.get("actor_motivations", []):
        for lens in ["structural_forces", "ideological_script", "material_interests"]:
            c = m.get(lens, {}).get("confidence", "ASSESSED")
            conf_labels.append(c)

    conf_order   = ["ESTABLISHED", "PROBABLE", "ASSESSED", "SPECULATIVE"]
    overall_conf = "ASSESSED"
    if conf_labels:
        counts       = {c: conf_labels.count(c) for c in conf_order}
        overall_conf = max(counts, key=counts.get)

    # Store in layer_outputs
    sb.table("layer_outputs").insert({
        "story_id":          story_id,
        "layer":             "WHY",
        "content":           result,
        "confidence_overall":overall_conf,
        "model_used":        GROQ_MODEL,
    }).execute()

    # Print synthesis
    print(f"\n  SYNTHESIS:")
    print(f"  {result.get('synthesis', '')}")
    print(f"\n  KEY VARIABLE:")
    print(f"  {result.get('key_variable', '')}")
    print(f"\n  CONFIDENCE:")
    print(f"  {result.get('confidence_assessment', '')}")
    print()

    for mot in result.get("actor_motivations", []):
        actor = mot.get("actor", "")
        print(f"  [{actor}]")

        struct = mot.get("structural_forces", {})
        print(f"    STRUCTURAL [{struct.get('confidence','?')}]: {struct.get('analysis','')[:100]}")

        ideo = mot.get("ideological_script", {})
        print(f"    IDEOLOGY [{ideo.get('confidence','?')}]: {ideo.get('doctrine','')} — {ideo.get('how_it_applies','')[:80]}")

        mat = mot.get("material_interests", {})
        gains = mat.get("gains", [])
        print(f"    MATERIAL [{mat.get('confidence','?')}]: gains={gains[:2]}")
        print()

    return result


def build_all_why() -> None:
    stories = sb.table("stories").select("id, headline").execute()
    for story in stories.data:
        build_why(story["id"])
        time.sleep(REQUEST_DELAY)


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if len(sys.argv) == 2:
        build_why(sys.argv[1])
    else:
        build_all_why()