"""
NewsGT — Pipeline Orchestrator
Runs the full analysis pipeline end to end for a given topic:
  1. GDELT ingestion
  2. Article content fetching
  3. 5W1H extraction
  4. Master fact set construction
  5. Bias analysis
  6. WHO layer
  7. HOW layer
  8. WHY layer
"""

import sys
import time
from dotenv import load_dotenv

load_dotenv()

from pipeline.ingestion.gdelt   import ingest_topic, ingest_all_categories
from pipeline.ingestion.fetcher import fetch_unprocessed
from pipeline.extraction.extractor    import extract_story
from pipeline.extraction.master_facts import build_master_facts
from pipeline.bias.analyzer           import analyze_story
from pipeline.analysis.who            import build_who
from pipeline.analysis.how            import build_how
from pipeline.analysis.why            import build_why


def run_pipeline(keyword: str, category: str,
                 timespan: str = "24h") -> dict | None:
    """
    Run full pipeline for a single topic.
    Returns the story_id if successful, None otherwise.
    """
    print(f"\n{'='*60}")
    print(f"NewsGT Pipeline")
    print(f"Topic:    {keyword}")
    print(f"Category: {category}")
    print(f"{'='*60}\n")

    # ── Step 1: Ingest ────────────────────────────────────────────────────────
    print("STEP 1 — GDELT Ingestion")
    ingest_result = ingest_topic(keyword, category, timespan=timespan)
    story_id      = ingest_result.get("story_id")

    if not story_id:
        print("  ⚠️  No story created — no matching articles found")
        return None

    print(f"  Story ID: {story_id}")
    time.sleep(2)

    # ── Step 2: Fetch content ─────────────────────────────────────────────────
    print("\nSTEP 2 — Fetch Article Content")
    fetch_unprocessed(story_id=story_id)
    time.sleep(1)

    # ── Step 3: Extract 5W1H ──────────────────────────────────────────────────
    print("\nSTEP 3 — 5W1H Extraction")
    extract_story(story_id)
    time.sleep(1)

    # ── Step 4: Master fact set ───────────────────────────────────────────────
    print("\nSTEP 4 — Master Fact Set")
    master = build_master_facts(story_id)
    if not master:
        print("  ⚠️  Master fact set failed")
        return None
    time.sleep(1)

    # ── Step 5: Bias analysis ─────────────────────────────────────────────────
    print("\nSTEP 5 — Bias Analysis")
    analyze_story(story_id)
    time.sleep(1)

    # ── Step 6: WHO ───────────────────────────────────────────────────────────
    print("\nSTEP 6 — WHO Layer")
    build_who(story_id)
    time.sleep(1)

    # ── Step 7: HOW ───────────────────────────────────────────────────────────
    print("\nSTEP 7 — HOW Layer")
    build_how(story_id)
    time.sleep(1)

    # ── Step 8: WHY ───────────────────────────────────────────────────────────
    print("\nSTEP 8 — WHY Layer")
    build_why(story_id)

    print(f"\n{'='*60}")
    print(f"✅ Pipeline complete — story_id: {story_id}")
    print(f"{'='*60}\n")

    return story_id


def run_all_categories(timespan: str = "24h") -> list[str]:
    """
    Run pipeline for the primary keyword of each of the 9 domains.
    Returns list of story_ids created.
    """
    from pipeline.ingestion.gdelt import CATEGORY_KEYWORDS

    story_ids = []
    for category, keywords in CATEGORY_KEYWORDS.items():
        keyword  = keywords[0]
        story_id = run_pipeline(keyword, category, timespan=timespan)
        if story_id:
            story_ids.append(story_id)
        time.sleep(5)  # Be respectful between categories

    print(f"\n{'='*60}")
    print(f"All categories done. {len(story_ids)} stories created.")
    return story_ids


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) == 3:
        # python -m pipeline.main "Iran strikes" "Middle East & Gulf"
        kw  = sys.argv[1]
        cat = sys.argv[2]
        run_pipeline(kw, cat)

    elif len(sys.argv) == 2 and sys.argv[1] == "all":
        # python -m pipeline.main all
        run_all_categories()

    else:
        print("Usage:")
        print('  python -m pipeline.main "keyword" "Category Label"')
        print('  python -m pipeline.main all')
        print()
        print("Categories:")
        from pipeline.ingestion.gdelt import CATEGORY_KEYWORDS
        for cat in CATEGORY_KEYWORDS:
            print(f'  "{cat}"')