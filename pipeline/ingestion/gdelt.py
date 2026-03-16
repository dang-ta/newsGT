"""
NewsGT — GDELT Ingestion
Fetches articles from GDELT DOC 2.0 API for a given topic/keyword.
Quality filters before storing. Known sources get rated credibility_weight,
unknown sources that pass quality filter get default 0.4.
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

GDELT_API          = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_MIN_INTERVAL = 6   # seconds between requests
_last_request_time = 0.0

# ── Domain map: source name → domain ─────────────────────────────────────────
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

DOMAIN_TO_SOURCE = {v: k for k, v in SOURCE_DOMAINS.items()}

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


# ── Helpers ───────────────────────────────────────────────────────────────────
def get_source_id_map() -> dict:
    result = sb.table("source_profiles").select("id, name").execute()
    name_to_id = {r["name"]: r["id"] for r in result.data}
    return {
        domain: name_to_id[name]
        for domain, name in DOMAIN_TO_SOURCE.items()
        if name in name_to_id
    }


def cluster_id_from_urls(urls: list[str]) -> str:
    combined = "|".join(sorted(urls))
    return hashlib.md5(combined.encode()).hexdigest()


def domain_from_url(url: str) -> str:
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc
    except Exception:
        return ""


def match_domain_to_source(url_domain: str, source_id_map: dict) -> str | None:
    if url_domain in source_id_map:
        return url_domain
    for known_domain in source_id_map:
        if url_domain == known_domain:
            return known_domain
        if url_domain.endswith("." + known_domain):
            return known_domain
    return None


def story_exists(cluster_id: str) -> bool:
    result = (
        sb.table("stories")
        .select("id")
        .eq("gdelt_cluster_id", cluster_id)
        .limit(1)
        .execute()
    )
    return len(result.data) > 0


def article_exists(url: str) -> bool:
    result = (
        sb.table("articles")
        .select("id")
        .eq("url", url)
        .limit(1)
        .execute()
    )
    return len(result.data) > 0


def get_or_create_unrated_source(domain: str) -> str:
    """Get or create a minimal source profile for unknown domains."""
    existing = (
        sb.table("source_profiles")
        .select("id")
        .eq("name", domain)
        .limit(1)
        .execute()
    )
    if existing.data:
        return existing.data[0]["id"]
    new_src = sb.table("source_profiles").insert({
        "name":               domain,
        "status":             "active",
        "mbfc_credibility":   "Mixed",
        "credibility_weight": 0.4,
        "manual_bias_profiles": {},
        "pattern_threshold":  {},
    }).execute()
    return new_src.data[0]["id"]


# ── GDELT request ─────────────────────────────────────────────────────────────
def _gdelt_request(params: dict) -> requests.Response:
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < GDELT_MIN_INTERVAL:
        time.sleep(GDELT_MIN_INTERVAL - elapsed)
    _last_request_time = time.time()
    return requests.get(GDELT_API, params=params, timeout=30)


def fetch_articles(keyword: str, timespan: str = "24h",
                   max_records: int = 250, retries: int = 3) -> list[dict]:
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
            return r.json().get("articles", [])
        except Exception as e:
            if attempt < retries - 1:
                print(f"  ⚠️  Fetch error, retrying in {10*(attempt+1)}s: {e}")
                time.sleep(10 * (attempt + 1))
            else:
                print(f"  ⚠️  GDELT fetch failed after {retries} attempts: {e}")
    return []


# ── Quality filter ────────────────────────────────────────────────────────────
def filter_articles(articles: list[dict],
                    source_id_map: dict) -> list[dict]:
    """
    Quality filter — keep articles with real signal, discard noise.
    Accepts articles from ANY source (including state media).
    Known sources get rated credibility_weight.
    Unknown sources that appear 2+ times get default 0.4.

    Filters out:
    - Missing domain or title
    - Domains appearing only once (low-traffic noise)
    - Non-English articles
    """
    # Count domain frequency
    domain_counts: dict[str, int] = {}
    for article in articles:
        d = domain_from_url(article.get("url", ""))
        if d:
            domain_counts[d] = domain_counts.get(d, 0) + 1

    result = []
    for article in articles:
        url    = article.get("url", "")
        title  = article.get("title", "").strip()
        lang   = article.get("language", "")
        domain = domain_from_url(url)

        if not domain or not title:
            continue
        if lang and lang.lower() not in ("english", "en"):
            continue
        if domain_counts.get(domain, 0) < 2:
            continue

        matched = match_domain_to_source(domain, source_id_map)
        if matched:
            article["_matched_domain"] = matched
            article["_source_id"]      = source_id_map[matched]
            article["_known_source"]   = True
        else:
            article["_matched_domain"] = domain
            article["_source_id"]      = None
            article["_known_source"]   = False

        result.append(article)

    return result


MAX_ARTICLES_PER_STORY = 10  # token budget: ~20K for extraction, ~80K for analysis


def select_diverse_articles(articles: list[dict],
                             max_count: int = MAX_ARTICLES_PER_STORY) -> list[dict]:
    """
    Select up to max_count articles prioritising source diversity.
    Known (rated) sources selected first — one per domain.
    Remaining slots filled from unknown sources.
    """
    known   = [a for a in articles if a.get("_known_source")]
    unknown = [a for a in articles if not a.get("_known_source")]

    # Deduplicate known sources — one article per source domain
    seen_domains: set[str] = set()
    diverse_known = []
    for a in known:
        d = a.get("_matched_domain", "")
        if d not in seen_domains:
            seen_domains.add(d)
            diverse_known.append(a)

    selected = diverse_known[:max_count]

    # Fill remaining slots with unknown sources (different domains)
    remaining = max_count - len(selected)
    if remaining > 0:
        seen_unknown: set[str] = set()
        for a in unknown:
            d = a.get("_matched_domain", "")
            if d not in seen_unknown and remaining > 0:
                seen_unknown.add(d)
                selected.append(a)
                remaining -= 1

    return selected


def assign_thread(category: str, headline: str) -> tuple[str | None, int]:
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
        return None, 1

    headline_words = set(headline.lower().split())
    for row in result.data:
        existing_words = set((row["headline"] or "").lower().split())
        if len(headline_words & existing_words) >= 3:
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

    return None, 1


# ── Core ingestion ────────────────────────────────────────────────────────────
def ingest_topic(keyword: str, category: str,
                 timespan: str = "24h") -> dict:
    print(f"\n── Ingesting: '{keyword}' [{category}] ──")
    source_id_map = get_source_id_map()

    # 1. Fetch
    raw_articles = fetch_articles(keyword, timespan=timespan)
    print(f"  GDELT returned: {len(raw_articles)} articles")

    if not raw_articles:
        return {"keyword": keyword, "fetched": 0, "stored": 0, "skipped": 0}

    # 2. Quality filter
    filtered = filter_articles(raw_articles, source_id_map)
    known    = sum(1 for a in filtered if a.get("_known_source"))
    unknown  = len(filtered) - known
    print(f"  After quality filter: {len(filtered)} articles "
          f"({known} rated, {unknown} unrated/default 0.4)")

    if not filtered:
        return {"keyword": keyword, "fetched": len(raw_articles),
                "stored": 0, "skipped": len(raw_articles)}

    # 3. Diverse selection — cap for token budget
    selected = select_diverse_articles(filtered)
    print(f"  Selected: {len(selected)}/{len(filtered)} "
          f"(capped at {MAX_ARTICLES_PER_STORY} for token budget)")

    # 4. Cluster ID from selected articles
    urls       = [a["url"] for a in selected]
    cluster_id = cluster_id_from_urls(urls)

    # 5. Skip if exists
    if story_exists(cluster_id):
        print(f"  Story already exists — skipping")
        return {"keyword": keyword, "fetched": len(raw_articles),
                "stored": 0, "skipped": len(selected)}

    # 6. Thread assignment
    headline              = selected[0].get("title", keyword)
    thread_id, thread_seq = assign_thread(category, headline)
    is_root               = thread_id is None

    # 7. Create story
    story_data = {
        "gdelt_cluster_id": cluster_id,
        "category_label":   category,
        "headline":         headline,
        "timestamp":        datetime.now(timezone.utc).isoformat(),
        "master_fact_set":  {},
        "master_version":   0,
        "thread_sequence":  thread_seq,
        "is_thread_root":   is_root,
    }
    if thread_id:
        story_data["thread_id"] = thread_id

    story_result = sb.table("stories").insert(story_data).execute()
    story_id     = story_result.data[0]["id"]

    if is_root:
        sb.table("stories").update({"thread_id": story_id}).eq("id", story_id).execute()

    print(f"  Story created: {story_id[:8]}... "
          f"({'root' if is_root else f'seq {thread_seq}'})")

    # 8. Store articles
    stored, skipped = 0, 0
    for article in selected:
        url = article.get("url", "")
        if not url or article_exists(url):
            skipped += 1
            continue

        # Resolve source_id
        source_id = article.get("_source_id")
        if not source_id:
            source_id = get_or_create_unrated_source(
                article.get("_matched_domain", "unknown")
            )

        seen_date = article.get("seendate", "")
        try:
            pub_date = datetime.strptime(
                seen_date, "%Y%m%dT%H%M%SZ"
            ).replace(tzinfo=timezone.utc).isoformat()
        except Exception:
            pub_date = datetime.now(timezone.utc).isoformat()

        try:
            sb.table("articles").insert({
                "source_id":        source_id,
                "story_id":         story_id,
                "gdelt_cluster_id": cluster_id,
                "url":              url,
                "raw_text":         "",
                "published_at":     pub_date,
                "language":         article.get("language", "English"),
                "processed":        False,
            }).execute()
            stored += 1
        except Exception as e:
            print(f"  ⚠️  Article insert failed ({url[:50]}...): {e}")
            skipped += 1

        time.sleep(0.05)

    print(f"  Articles stored: {stored}  skipped: {skipped}")
    return {
        "keyword":    keyword,
        "cluster_id": cluster_id,
        "story_id":   story_id,
        "fetched":    len(raw_articles),
        "filtered":   len(filtered),
        "selected":   len(selected),
        "stored":     stored,
        "skipped":    skipped,
    }


def ingest_all_categories(timespan: str = "24h") -> list[dict]:
    results = []
    for category, keywords in CATEGORY_KEYWORDS.items():
        result = ingest_topic(keywords[0], category, timespan=timespan)
        results.append(result)
        time.sleep(1)
    return results


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        result = ingest_topic(sys.argv[1], sys.argv[2])
        print(f"\nResult: {result}")
    elif len(sys.argv) == 2 and sys.argv[1] == "all":
        results = ingest_all_categories()
        print(f"\nTotal stored: {sum(r.get('stored', 0) for r in results)}")
    else:
        print("Usage:")
        print('  python gdelt.py "keyword" "Category Label"')
        print('  python gdelt.py all')