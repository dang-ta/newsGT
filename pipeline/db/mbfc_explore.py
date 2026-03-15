"""
NewsGT — MBFC Dataset Explorer
Finds the best available sources per domain from the Idiap MBFC dataset.
Use this to select our final source universe from what's actually in the data.
"""

import pandas as pd
from datasets import load_dataset

# ── Load ──────────────────────────────────────────────────────────────────────
print("Loading MBFC dataset...")
ds = load_dataset("sergioburdisso/news_media_bias_and_factuality", split="train")
df = pd.DataFrame(ds)
print(f"  {len(df)} sources loaded\n")

# ── Credibility weight mapping ────────────────────────────────────────────────
FACTUAL_TO_WEIGHT = {
    "very high": 1.0,
    "high":      0.8,
    "mixed":     0.4,
    "low":       0.2,
    "very low":  0.1,
}

df["credibility_weight"] = df["factual_reporting"].str.lower().map(FACTUAL_TO_WEIGHT).fillna(0.4)

# ── Filter: only High or Very High factual reporting ──────────────────────────
high_cred = df[df["credibility_weight"] >= 0.8].copy()
print(f"High/Very High credibility sources: {len(high_cred)}\n")

# ── Domain-relevant keyword map ───────────────────────────────────────────────
# For each domain, search source names for relevant keywords
DOMAIN_KEYWORDS = {
    "Middle East & Gulf": [
        "aljazeera", "haaretz", "jpost", "jerusalem", "arabnews", "middleeast",
        "presstv", "dawn", "arab", "gulf", "israel", "iran", "palestine",
        "alarabiya", "asharq", "thenational"
    ],
    "US Politics & Foreign Policy": [
        "nytimes", "washingtonpost", "wsj", "apnews", "reuters", "bloomberg",
        "foreignpolicy", "theintercept", "politico", "thehill", "axios",
        "npr", "pbs", "csmonitor", "foreignaffairs"
    ],
    "Russia / Ukraine / NATO": [
        "rt.com", "tass", "kyivpost", "kyiv", "ukrinform", "euractiv",
        "rferl", "meduza", "moskva", "ukraine", "russia", "sputnik"
    ],
    "China / Taiwan / Indo-Pacific": [
        "scmp", "cgtn", "xinhua", "nikkei", "straitstimes", "taipeitimes",
        "asiatimes", "thediplomat", "chinadaily", "cna"
    ],
    "Global Economy & Trade Wars": [
        "bloomberg", "ft.com", "economist", "reuters", "wsj", "imf",
        "worldbank", "nikkei", "businessinsider", "cnbc", "marketwatch"
    ],
    "South Asia": [
        "thehindu", "timesofindia", "dawn", "thedailystar", "thewire",
        "ndtv", "hindustantimes", "tribuneindia", "business-standard",
        "pakistantoday", "geo.tv"
    ],
    "Africa & Resources": [
        "dailymaverick", "allafrica", "theeastafrican", "nation.africa",
        "businessday", "premiumtimesng", "mg.co.za", "citizen.co.za",
        "monitor.co.ug", "africa"
    ],
    "Technology & AI Power": [
        "wired", "techcrunch", "arstechnica", "theverge", "mit",
        "technologyreview", "zdnet", "venturebeat", "ieee"
    ],
    "Climate & Energy Transition": [
        "carbonbrief", "climatecentral", "insideclimatenews", "guardian",
        "bloomberg", "reuters", "ft.com", "energymonitor", "renewableenergyworld"
    ],
}

# ── Find candidates per domain ────────────────────────────────────────────────
print("=" * 80)
print("TOP CANDIDATES PER DOMAIN (High/Very High credibility only)")
print("=" * 80)

all_candidates = {}

for domain, keywords in DOMAIN_KEYWORDS.items():
    print(f"\n── {domain} ──")
    matches = pd.DataFrame()
    for kw in keywords:
        hits = high_cred[high_cred["source"].str.contains(kw, case=False, na=False)]
        matches = pd.concat([matches, hits]).drop_duplicates(subset="source")

    if matches.empty:
        print("  No matches found")
        continue

    # Sort by credibility weight desc, then bias toward neutral/center
    matches = matches.sort_values("credibility_weight", ascending=False)

    print(f"  {'Source':<35} {'Factual':<12} {'Bias':<20} {'Weight'}")
    print(f"  {'-'*80}")
    for _, row in matches.head(10).iterrows():
        print(f"  {row['source']:<35} {row['factual_reporting']:<12} {row['bias']:<20} {row['credibility_weight']}")

    all_candidates[domain] = matches.head(10)

# ── Wire services (always include) ───────────────────────────────────────────
print("\n── Wire Services (always include) ──")
wire_keywords = ["reuters", "apnews", "afp", "ap.org"]
wires = pd.DataFrame()
for kw in wire_keywords:
    hits = df[df["source"].str.contains(kw, case=False, na=False)]
    wires = pd.concat([wires, hits]).drop_duplicates(subset="source")
print(f"  {'Source':<35} {'Factual':<12} {'Bias':<20} {'Weight'}")
print(f"  {'-'*80}")
for _, row in wires.iterrows():
    print(f"  {row['source']:<35} {row['factual_reporting']:<12} {row['bias']:<20} {row['credibility_weight']}")

# ── State media (low cred but needed for narrative) ───────────────────────────
print("\n── State/Narrative Sources (Mixed/Low — included deliberately) ──")
state_keywords = ["rt.com", "cgtn", "presstv", "tass", "xinhua", "sputnik"]
state = pd.DataFrame()
for kw in state_keywords:
    hits = df[df["source"].str.contains(kw, case=False, na=False)]
    state = pd.concat([state, hits]).drop_duplicates(subset="source")
print(f"  {'Source':<35} {'Factual':<12} {'Bias':<20} {'Weight'}")
print(f"  {'-'*80}")
for _, row in state.iterrows():
    print(f"  {row['source']:<35} {row['factual_reporting']:<12} {row['bias']:<20} {row['credibility_weight']}")

print("\n✅ Done. Use this output to finalize the source universe.")