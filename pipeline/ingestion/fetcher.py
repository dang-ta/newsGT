"""
NewsGT — Article Content Fetcher
Fetches full text from article URLs for unprocessed articles.
Stores raw_text in articles table and marks processed = True.
Uses trafilatura for clean content extraction.
"""

import os
import time
import trafilatura
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))

# ── Config ────────────────────────────────────────────────────────────────────
FETCH_DELAY     = 2.0   # seconds between requests — be respectful
MIN_TEXT_LENGTH = 200   # discard articles shorter than this (likely paywalled)
MAX_RETRIES     = 2


# ── Fetch single article ──────────────────────────────────────────────────────
def fetch_article_text(url: str) -> str | None:
    """
    Fetch and extract clean text from a URL using trafilatura.
    Returns None if extraction fails or content too short.
    """
    for attempt in range(MAX_RETRIES):
        try:
            downloaded = trafilatura.fetch_url(url)
            if not downloaded:
                return None

            text = trafilatura.extract(
                downloaded,
                include_comments=False,
                include_tables=False,
                no_fallback=False,
                favor_recall=True,
            )

            if not text or len(text.strip()) < MIN_TEXT_LENGTH:
                return None

            return text.strip()

        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep(2)
            else:
                print(f"    ⚠️  Fetch error ({url[:50]}...): {e}")
    return None


# ── Batch fetcher ─────────────────────────────────────────────────────────────
def fetch_unprocessed(story_id: str = None,
                      limit: int = 50) -> dict:
    """
    Fetch content for all unprocessed articles.
    Optionally filter by story_id.
    Returns summary of results.
    """
    # Build query
    query = (
        sb.table("articles")
        .select("id, url, source_profiles(name)")
        .eq("processed", False)
        .limit(limit)
    )
    if story_id:
        query = query.eq("story_id", story_id)

    result = query.execute()
    articles = result.data

    if not articles:
        print("  No unprocessed articles found.")
        return {"fetched": 0, "failed": 0, "skipped": 0}

    print(f"  Processing {len(articles)} articles...")
    fetched, failed, skipped = 0, 0, 0

    for article in articles:
        article_id = article["id"]
        url = article["url"]
        source = article.get("source_profiles", {}).get("name", "unknown")

        print(f"  [{source}] {url[:70]}...")

        text = fetch_article_text(url)

        if text:
            sb.table("articles").update({
                "raw_text":  text,
                "processed": True,
            }).eq("id", article_id).execute()
            print(f"    ✅ {len(text):,} chars")
            fetched += 1
        else:
            # Mark as processed even if failed — avoids retrying paywalled articles
            sb.table("articles").update({
                "raw_text":  "",
                "processed": True,
            }).eq("id", article_id).execute()
            print(f"    ❌ Failed (paywall or extraction error)")
            failed += 1

        time.sleep(FETCH_DELAY)

    total = fetched + failed + skipped
    print(f"\n  Done: {fetched} fetched, {failed} failed, {skipped} skipped / {total} total")
    return {"fetched": fetched, "failed": failed, "skipped": skipped}


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) == 2:
        # python fetcher.py <story_id>
        result = fetch_unprocessed(story_id=sys.argv[1])
    else:
        # python fetcher.py  — fetch all unprocessed
        result = fetch_unprocessed()

    print(f"\nResult: {result}")