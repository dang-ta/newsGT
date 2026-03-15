"""
NewsGT — GDELT Ingestion
Fetches articles from GDELT DOC 2.0 API for a given topic/keyword,
filters against our source universe, and stores into stories + articles tables.
"""

import os
import hashlib
import time
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))

# ── Domain map: source name → domain (mirrors seed_sources.py) ───────────────
SOURCE_DOMAINS = {
    "Reuters":                  "reuters.com",
    "Associated Press":         "apnews.com",
    "AFP":                      "afp.com",
    "BBC":                      "bbc.com",
    "New York Times":           "nytimes.com",
    "Financial Times":          "ft.com",
    "The Economist":            "economist.com",
    "Bloomberg":                "bloomberg.com",
    "NPR":                      "npr.org",
    "PBS":                      "pbs.org",
    "Axios":                    "axios.com",
    "Christian Science Monitor":"csmonitor.com",
    "Kyiv Independent":         "kyivindependent.com",
    "Euractiv":                 "euractiv.com",
    "Meduza":                   "meduza.io",
    "Nikkei":                   "nikkei.com",
    "The Diplomat":             "thediplomat.com",
    "Asia Times":               "asiatimes.com",
    "Haaretz":                  "haaretz.com",
    "Jerusalem Post":           "jpost.com",
    "Times of Israel":          "timesofisrael.com",
    "Daily Maverick":           "dailymaverick.co.za",
    "AllAfrica":                "allafrica.com",
    "Africa Check":             "africacheck.org",
    "Wired":                    "wired.com",
    "Ars Technica":             "arstechnica.com",
    "MIT Technology Review":    "technologyreview.com",
    "Carbon Brief":             "carbonbrief.org",
    "Climate Central":          "climatecentral.org",
    "Al Jazeera":               "aljazeera.com",
    "RT":                       "rt.com",
    "CGTN":                     "cgtn.com",
    "Dawn":                     "dawn.com",
    "The Hindu":                "thehindu.com",
    "Times of India":           "timesofindia.com",
    "South China Morning Post": "scmp.com",
    "Arab News":                "arabnews.com",
}

# Reverse map: domain → source name
DOMAIN_TO_SOURCE = {v: k for k, v in SOURCE_DOMAINS.items()}

# All domains in our universe
ALL_DOMAINS = list(SOURCE_DOMAINS.values())

# ── Category → GDELT keyword map ──────────────────────────────────────────────
CATEGORY_KEYWORDS = {
    "Middle East & Gulf":           ["Gaza", "Israel", "Iran", "Hamas", "Hezbollah",
                                     "West Bank", "Saudi Arabia", "Yemen", "Lebanon"],
    "US Politics & Foreign Policy": ["Trump", "White House", "Congress", "Pentagon",
                                     "State Department", "US foreign policy"],
    "Russia / Ukraine / NATO":      ["Ukraine", "Russia", "NATO", "Zelensky", "Putin",
                                     "Kremlin", "Kyiv", "Moscow"],
    "China / Taiwan / Indo-Pacific":["China", "Taiwan", "Xi Jinping", "South China Sea",
                                     "Beijing", "Indo-Pacific", "ASEAN"],
    "Global Economy & Trade Wars":  ["tariffs", "trade war", "sanctions", "Federal Reserve",
                                     "inflation", "recession", "IMF", "World Bank"],
    "South Asia":                   ["India", "Pakistan", "Modi", "Kashmir",
                                     "Bangladesh", "Afghanistan", "Sri Lanka"],
    "Africa & Resources":           ["Africa", "Congo", "Nigeria", "Ethiopia",
                                     "critical minerals", "cobalt", "lithium", "Wagner"],
    "Technology & AI Power":        ["artificial intelligence", "semiconductors",
                                     "chip war", "Nvidia", "cybersecurity", "AI regulation"],
    "Climate & Energy Transition":  ["climate change", "COP30", "carbon emissions",
                                     "renewable energy", "fossil fuels", "oil prices"],
}


GDELT_API = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_MIN_INTERVAL = 6  # seconds between requests (limit is 1 per 5s)
_last_request_time = 0.0


def _gdelt_request(params: dict) -> requests.Response:
    """Enforce rate limit and make GDELT request."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < GDELT_MIN_INTERVAL:
        wait = GDELT_MIN_INTERVAL - elapsed
        time.sleep(wait)
    _last_request_time = time.time()
    return requests.get(GDELT_API, params=params, timeout=30)


# ── Helpers ───────────────────────────────────────────────────────────────────
def get_source_id_map() -> dict:
    """Fetch source_id for each domain from source_profiles."""
    result = sb.table("source_profiles").select("id, name").execute()
    name_to_id = {r["name"]: r["id"] for r in result.data}
    return {
        domain: name_to_id[name]
        for domain, name in DOMAIN_TO_SOURCE.items()
        if name in name_to_id
    }


def cluster_id_from_urls(urls: list[str]) -> str:
    """Generate a stable cluster ID from the set of article URLs."""
    combined = "|".join(sorted(urls))
    return hashlib.md5(combined.encode()).hexdigest()


def domain_from_url(url: str) -> str:
    """Extract base domain from URL."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        # Strip www.
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc
    except Exception:
        return ""


def match_domain_to_source(url_domain: str, source_id_map: dict) -> str | None:
    """Match article domain to one of our source domains."""
    # Exact match first
    if url_domain in source_id_map:
        return url_domain
    # Subdomain match only: url_domain must END with .known_domain
    # e.g. asia.nikkei.com → nikkei.com  ✅
    # e.g. breitbart.com → rt.com        ❌
    for known_domain in source_id_map:
        if url_domain == known_domain:
            return known_domain
        if url_domain.endswith("." + known_domain):
            return known_domain
    return None


def story_exists(cluster_id: str) -> bool:
    """Check if story already exists in DB."""
    result = (
        sb.table("stories")
        .select("id")
        .eq("gdelt_cluster_id", cluster_id)
        .limit(1)
        .execute()
    )
    return len(result.data) > 0


def article_exists(url: str) -> bool:
    """Check if article already exists in DB."""
    result = (
        sb.table("articles")
        .select("id")
        .eq("url", url)
        .limit(1)
        .execute()
    )
    return len(result.data) > 0


# ── Core ingestion ────────────────────────────────────────────────────────────
def fetch_articles(keyword: str, timespan: str = "24h",
                   max_records: int = 250,
                   retries: int = 3) -> list[dict]:
    """Fetch articles from GDELT DOC API directly via requests with retry."""
    params = {
        "query":      f"{keyword} sourcelang:english",
        "mode":       "artlist",
        "maxrecords": str(min(max_records, 250)),
        "timespan":   timespan,
        "format":     "json",
    }
    for attempt in range(retries):
        try:
            r = _gdelt_request(params)
            if r.status_code == 429:
                wait = 30 * (attempt + 1)
                print(f"  Rate limited — waiting {wait}s (attempt {attempt+1}/{retries})")
                time.sleep(wait)
                continue
            r.raise_for_status()
            data = r.json()
            return data.get("articles", [])
        except Exception as e:
            if attempt < retries - 1:
                wait = 10 * (attempt + 1)
                print(f"  ⚠️  Fetch error, retrying in {wait}s: {e}")
                time.sleep(wait)
            else:
                print(f"  ⚠️  GDELT fetch failed after {retries} attempts: {e}")
    return []


def filter_to_universe(articles: list[dict],
                        source_id_map: dict) -> list[dict]:
    """Keep only articles from our source universe."""
    filtered = []
    for article in articles:
        url = article.get("url", "")
        domain = domain_from_url(url)
        matched = match_domain_to_source(domain, source_id_map)
        if matched:
            article["_matched_domain"] = matched
            article["_source_id"] = source_id_map[matched]
            filtered.append(article)
    return filtered


def assign_thread(category: str, headline: str) -> tuple[str | None, int]:
    """
    Find existing thread for this category or return None to create new.
    Simple approach: find most recent thread root in same category
    from last 7 days with keyword overlap.
    Returns (thread_id, sequence_number).
    """
    # Find recent stories in same category
    result = (
        sb.table("stories")
        .select("id, thread_id, thread_sequence, headline, is_thread_root")
        .eq("category_label", category)
        .eq("is_thread_root", True)
        .order("created_at", desc=True)
        .limit(10)
        .execute()
    )

    if not result.data:
        return None, 1  # No existing thread — this becomes root

    # Simple keyword overlap check
    headline_words = set(headline.lower().split())
    for row in result.data:
        existing_words = set((row["headline"] or "").lower().split())
        overlap = len(headline_words & existing_words)
        if overlap >= 3:  # At least 3 words in common
            # Find current max sequence in this thread
            thread_id = row["thread_id"] or row["id"]
            seq_result = (
                sb.table("stories")
                .select("thread_sequence")
                .eq("thread_id", thread_id)
                .order("thread_sequence", desc=True)
                .limit(1)
                .execute()
            )
            next_seq = (seq_result.data[0]["thread_sequence"] or 0) + 1 if seq_result.data else 2
            return thread_id, next_seq

    return None, 1  # No matching thread — new root


def ingest_topic(keyword: str, category: str,
                 timespan: str = "24h") -> dict:
    """
    Full ingestion pipeline for a keyword + category:
    1. Fetch from GDELT
    2. Filter to source universe
    3. Create story record
    4. Store articles
    Returns summary dict.
    """
    print(f"\n── Ingesting: '{keyword}' [{category}] ──")
    source_id_map = get_source_id_map()

    # 1. Fetch
    raw_articles = fetch_articles(keyword, timespan=timespan)
    print(f"  GDELT returned: {len(raw_articles)} articles")

    if not raw_articles:
        return {"keyword": keyword, "fetched": 0, "stored": 0, "skipped": 0}

    # 2. Filter to universe
    universe_articles = filter_to_universe(raw_articles, source_id_map)
    print(f"  In our universe: {len(universe_articles)} articles")

    if not universe_articles:
        return {"keyword": keyword, "fetched": len(raw_articles),
                "stored": 0, "skipped": len(raw_articles)}

    # 3. Generate cluster ID
    urls = [a["url"] for a in universe_articles]
    cluster_id = cluster_id_from_urls(urls)

    # 4. Skip if story already exists
    if story_exists(cluster_id):
        print(f"  Story already exists (cluster: {cluster_id[:8]}...) — skipping")
        return {"keyword": keyword, "fetched": len(raw_articles),
                "stored": 0, "skipped": len(universe_articles)}

    # 5. Thread assignment
    headline = universe_articles[0].get("title", keyword)
    thread_id, thread_seq = assign_thread(category, headline)
    is_root = thread_id is None

    # 6. Create story record
    story_data = {
        "gdelt_cluster_id":  cluster_id,
        "category_label":    category,
        "headline":          headline,
        "timestamp":         datetime.now(timezone.utc).isoformat(),
        "master_fact_set":   {},
        "master_version":    0,
        "thread_sequence":   thread_seq,
        "is_thread_root":    is_root,
    }
    if thread_id:
        story_data["thread_id"] = thread_id

    story_result = sb.table("stories").insert(story_data).execute()
    story_id = story_result.data[0]["id"]

    # If this is root, set thread_id = its own id
    if is_root:
        sb.table("stories").update(
            {"thread_id": story_id}
        ).eq("id", story_id).execute()

    print(f"  Story created: {story_id[:8]}... "
          f"({'root' if is_root else f'seq {thread_seq}'})")

    # 7. Store articles
    stored, skipped = 0, 0
    for article in universe_articles:
        url = article.get("url", "")
        if not url or article_exists(url):
            skipped += 1
            continue

        # Parse published date
        seen_date = article.get("seendate", "")
        try:
            pub_date = datetime.strptime(
                seen_date, "%Y%m%dT%H%M%SZ"
            ).replace(tzinfo=timezone.utc).isoformat()
        except Exception:
            pub_date = datetime.now(timezone.utc).isoformat()

        article_data = {
            "source_id":        article["_source_id"],
            "story_id":         story_id,
            "gdelt_cluster_id": cluster_id,
            "url":              url,
            "raw_text":         "",           # Fetched separately by extractor
            "published_at":     pub_date,
            "language":         article.get("language", "English"),
            "processed":        False,
        }
        try:
            sb.table("articles").insert(article_data).execute()
            stored += 1
        except Exception as e:
            print(f"  ⚠️  Article insert failed ({url[:50]}...): {e}")
            skipped += 1

        time.sleep(0.05)  # Gentle rate limiting

    print(f"  Articles stored: {stored}  skipped: {skipped}")
    return {
        "keyword":   keyword,
        "cluster_id": cluster_id,
        "story_id":  story_id,
        "fetched":   len(raw_articles),
        "universe":  len(universe_articles),
        "stored":    stored,
        "skipped":   skipped,
    }


def ingest_all_categories(timespan: str = "24h") -> list[dict]:
    """Run ingestion for all 9 categories using their primary keywords."""
    results = []
    for category, keywords in CATEGORY_KEYWORDS.items():
        # Use first keyword as primary for now
        # Phase 2: run multiple keywords per category
        primary_keyword = keywords[0]
        result = ingest_topic(primary_keyword, category, timespan=timespan)
        results.append(result)
        time.sleep(1)  # Be respectful to GDELT
    return results


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 3:
        # python gdelt.py "Iran strikes" "Middle East & Gulf"
        kw = sys.argv[1]
        cat = sys.argv[2]
        result = ingest_topic(kw, cat)
        print(f"\nResult: {result}")
    elif len(sys.argv) == 2 and sys.argv[1] == "all":
        # python gdelt.py all
        results = ingest_all_categories()
        print(f"\n{'='*50}")
        print(f"Ingested {len(results)} categories")
        total_stored = sum(r.get("stored", 0) for r in results)
        print(f"Total articles stored: {total_stored}")
    else:
        print("Usage:")
        print('  python gdelt.py "keyword" "Category Label"')
        print('  python gdelt.py all')