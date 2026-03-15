"""
NewsGT — 5W1H Extractor
Extracts structured Who/What/When/Where/Why/How from article text
using Gemini 2.5 Flash with Chain-of-Thought prompting.
Stores output in article_extractions table.
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

# ── Config ────────────────────────────────────────────────────────────────────
GROQ_MODEL    = "llama-3.3-70b-versatile"
REQUEST_DELAY = 1.0  # seconds between requests (Groq is fast, be gentle)

# ── Prompt ────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a structured information extraction engine.
Your task is to extract factual claims from a news article using the 5W1H framework.

RULES:
- Extract ONLY what is explicitly stated in the article. No inference.
- Use neutral language. Strip emotional loading and framing.
- If a field cannot be determined from the article, return null.
- For WHO, list all named actors (people, organizations, states).
- For WHAT, describe the core action or event in one sentence.
- For WHEN, extract the most specific time reference available.
- For WHERE, extract the most specific location reference available.
- For WHY, extract only stated reasons — not inferred motivations.
- For HOW, extract the method or mechanism described.

Return ONLY valid JSON. No preamble, no explanation, no markdown.

JSON format:
{
  "who": {
    "actors": [
      {
        "name": "string",
        "type": "person|organization|state|group",
        "role": "what role they play in this event"
      }
    ]
  },
  "what": "string — the core event in one neutral sentence",
  "when_text": "string — time reference from article or null",
  "where_text": "string — location from article or null",
  "why": "string — stated reason only, or null if not stated",
  "how": "string — method or mechanism, or null if not stated",
  "key_claims": [
    "string — each distinct verifiable factual claim as a separate item"
  ]
}"""


# ── Extraction ────────────────────────────────────────────────────────────────
def extract_5w1h(raw_text: str, url: str = "") -> dict | None:
    """
    Extract 5W1H from article text using Gemini Flash.
    Returns parsed dict or None on failure.
    """
    if not raw_text or len(raw_text.strip()) < 100:
        return None

    # Truncate to ~3000 chars to leave room for output tokens
    text = raw_text[:3000]

    prompt = f"""Extract the 5W1H from this news article:

---
{text}
---

Return only valid JSON as specified."""

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.0,
            max_tokens=4000,
        )

        raw = response.choices[0].message.content.strip()

        # Strip markdown fences if present
        if "```" in raw:
            parts = raw.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    raw = part
                    break

        # Find JSON object boundaries
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start == -1 or end == 0:
            print(f"    ⚠️  No JSON object found in response")
            print(f"    Raw (first 300): {raw[:300]}")
            return None
        raw = raw[start:end]

        return json.loads(raw)

    except json.JSONDecodeError as e:
        print(f"    ⚠️  JSON parse error: {e}")
        print(f"    Raw (first 300): {raw[:300]}")
        return None
    except Exception as e:
        print(f"    ⚠️  Gemini error: {e}")
        return None


def extraction_exists(article_id: str) -> bool:
    """Check if extraction already exists for this article."""
    result = (
        sb.table("article_extractions")
        .select("id")
        .eq("article_id", article_id)
        .limit(1)
        .execute()
    )
    return len(result.data) > 0


# ── Batch processor ───────────────────────────────────────────────────────────
def extract_story(story_id: str) -> dict:
    """
    Run 5W1H extraction on all processed articles for a story.
    Stores results in article_extractions.
    Returns summary.
    """
    # Get story master_version
    story = sb.table("stories").select("master_version").eq("id", story_id).execute()
    master_version = story.data[0]["master_version"] if story.data else 0

    # Get processed articles for this story
    articles = (
        sb.table("articles")
        .select("id, url, raw_text, source_id")
        .eq("story_id", story_id)
        .eq("processed", True)
        .execute()
    )

    if not articles.data:
        print(f"  No processed articles for story {story_id[:8]}...")
        return {"extracted": 0, "failed": 0, "skipped": 0}

    print(f"  Extracting {len(articles.data)} articles for story {story_id[:8]}...")
    extracted, failed, skipped = 0, 0, 0

    for article in articles.data:
        article_id = article["id"]
        url        = article["url"]
        raw_text   = article.get("raw_text", "")

        # Skip if already extracted
        if extraction_exists(article_id):
            skipped += 1
            continue

        if not raw_text or len(raw_text.strip()) < 100:
            print(f"    ⏭  Skipping (no content): {url[:60]}")
            skipped += 1
            continue

        print(f"    Extracting: {url[:70]}...")
        result = extract_5w1h(raw_text, url)

        if result:
            extraction_data = {
                "article_id":     article_id,
                "source_id":      article["source_id"],
                "story_id":       story_id,
                "who":            result.get("who", {}),
                "what":           result.get("what"),
                "when_text":      result.get("when_text"),
                "where_text":     result.get("where_text"),
                "why":            result.get("why"),
                "how":            result.get("how"),
                "raw_extraction": result,
                "master_version": master_version,
            }
            sb.table("article_extractions").insert(extraction_data).execute()
            print(f"    ✅ what: {str(result.get('what', ''))[:80]}")
            extracted += 1
        else:
            print(f"    ❌ Extraction failed")
            failed += 1

        time.sleep(REQUEST_DELAY)

    print(f"\n  Done: {extracted} extracted, {failed} failed, {skipped} skipped")
    return {"extracted": extracted, "failed": failed, "skipped": skipped}


def extract_all_pending() -> list[dict]:
    """Run extraction on all stories with unextracted articles."""
    # Find stories that have processed articles but missing extractions
    stories = sb.table("stories").select("id, headline, category_label").execute()
    results = []
    for story in stories.data:
        story_id = story["id"]
        headline = (story.get("headline") or "")[:60]
        print(f"\n── Story: {headline} ──")
        result = extract_story(story_id)
        result["story_id"] = story_id
        results.append(result)
    return results


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) == 2:
        # python extractor.py <story_id>
        results = extract_story(sys.argv[1])
        print(f"\nResult: {results}")
    else:
        # python extractor.py — extract all pending
        results = extract_all_pending()
        total = sum(r.get("extracted", 0) for r in results)
        print(f"\nTotal extracted: {total}")