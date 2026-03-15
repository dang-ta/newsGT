"""
NewsGT — WHO Layer
Builds a declared actor map from article_extractions and behavioral_records.
Declared actors only — documented roles, observable interests.
No hidden actors, no inference beyond publicly established facts.
Stores result in layer_outputs table (layer = 'WHO').
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

# ── WHO prompt ────────────────────────────────────────────────────────────────
WHO_PROMPT = """You are a geopolitical actor analysis engine.

You will be given:
1. A verified event sequence (facts agreed upon across multiple sources)
2. Actor framing data — how each source positions each actor
3. A list of all actors mentioned across sources

Your task: build a DECLARED ACTOR MAP.

RULES:
- Include ONLY actors with documented roles in this specific event
- No hidden actors, no speculation about behind-the-scenes players
- Each actor must have: name, type, stated position, documented interest
- Stated position = what they officially say they want
- Documented interest = what they materially stand to gain/lose (observable, not inferred)
- Note how different sources frame each actor differently

Return ONLY valid JSON:
{
  "actors": [
    {
      "name": "string",
      "type": "state|organization|person|group",
      "stated_position": "string — their official public position on this event",
      "documented_interest": "string — material stake, observable from public record",
      "role_in_event": "string — what they actually did in this event",
      "source_framing": {
        "source_name": "agent|patient|neutral"
      },
      "confidence": "ESTABLISHED|PROBABLE|ASSESSED|SPECULATIVE"
    }
  ],
  "actor_relationships": [
    {
      "actor_a": "string",
      "actor_b": "string",
      "relationship": "string — nature of relationship in this event",
      "type": "alliance|conflict|negotiation|dependency"
    }
  ]
}"""


def build_who(story_id: str) -> dict:
    """Build WHO layer for a story."""

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

    story      = story_result.data[0]
    category   = story["category_label"]
    master_fs  = story.get("master_fact_set") or {}
    headline   = (story.get("headline") or "")[:60]

    print(f"\n── WHO: {headline} ──")

    # Load extractions for actor data
    extractions = (
        sb.table("article_extractions")
        .select("who, source_profiles(name)")
        .eq("story_id", story_id)
        .execute()
    ).data

    # Load behavioral records for framing data
    behavioral = (
        sb.table("behavioral_records")
        .select("framing_scores, source_profiles(name)")
        .eq("story_id", story_id)
        .execute()
    ).data

    # Aggregate actors across all extractions
    all_actors: dict[str, dict] = {}
    for ext in extractions:
        source_name = (ext.get("source_profiles") or {}).get("name", "Unknown")
        who_data    = ext.get("who") or {}
        for actor in who_data.get("actors", []):
            name = actor.get("name", "").strip()
            if not name:
                continue
            if name not in all_actors:
                all_actors[name] = {
                    "name":    name,
                    "type":    actor.get("type", "organization"),
                    "sources": [],
                    "roles":   [],
                }
            all_actors[name]["sources"].append(source_name)
            all_actors[name]["roles"].append(actor.get("role", ""))

    # Aggregate framing per actor from behavioral records
    framing_by_actor: dict[str, dict] = {}
    for rec in behavioral:
        source_name  = (rec.get("source_profiles") or {}).get("name", "Unknown")
        framing      = (rec.get("framing_scores") or {}).get("actors", [])
        for f in framing:
            actor_name = f.get("name", "").strip()
            if not actor_name:
                continue
            if actor_name not in framing_by_actor:
                framing_by_actor[actor_name] = {}
            framing_by_actor[actor_name][source_name] = f.get("role", "neutral")

    # Build prompt context
    actors_summary = []
    for name, data in all_actors.items():
        framing = framing_by_actor.get(name, {})
        actors_summary.append({
            "name":            name,
            "type":            data["type"],
            "mentioned_by":    list(set(data["sources"])),
            "source_framing":  framing,
        })

    prompt = f"""VERIFIED EVENT SEQUENCE:
{json.dumps(master_fs.get('verified_sequence', []), indent=2)}

ACTORS ACROSS SOURCES:
{json.dumps(actors_summary, indent=2)}

CATEGORY: {category}

Build the declared actor map. Return only valid JSON."""

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": WHO_PROMPT},
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
            print("  ⚠️  No JSON found in WHO response")
            return {}

        result = json.loads(raw[start:end])

    except Exception as e:
        print(f"  ⚠️  WHO LLM error: {e}")
        return {}

    # Store in layer_outputs
    sb.table("layer_outputs").insert({
        "story_id":          story_id,
        "layer":             "WHO",
        "content":           result,
        "confidence_overall":"PROBABLE",
        "model_used":        GROQ_MODEL,
    }).execute()

    # Print output
    print(f"  ✅ {len(result.get('actors', []))} actors identified\n")
    for actor in result.get("actors", []):
        print(f"  [{actor.get('type','?').upper()}] {actor.get('name','')}")
        print(f"    Position:  {actor.get('stated_position','')[:80]}")
        print(f"    Interest:  {actor.get('documented_interest','')[:80]}")
        print(f"    Role:      {actor.get('role_in_event','')[:80]}")
        framing = actor.get("source_framing", {})
        if framing:
            framing_str = " | ".join(f"{s}: {r}" for s, r in framing.items())
            print(f"    Framing:   {framing_str[:100]}")
        print()

    rels = result.get("actor_relationships", [])
    if rels:
        print(f"  Relationships:")
        for rel in rels:
            print(f"    {rel.get('actor_a','')} ←→ {rel.get('actor_b','')} "
                  f"[{rel.get('type','')}]: {rel.get('relationship','')[:60]}")

    return result


def build_all_who() -> None:
    """Build WHO layer for all stories."""
    stories = sb.table("stories").select("id, headline").execute()
    for story in stories.data:
        build_who(story["id"])
        time.sleep(REQUEST_DELAY)


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if len(sys.argv) == 2:
        build_who(sys.argv[1])
    else:
        build_all_who()