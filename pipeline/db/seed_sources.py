"""
NewsGT — Source Profiles Seed v2
Hybrid approach:
  - Dataset sources: pulled from Idiap/MBFC HuggingFace dataset
  - Manual sources: hardcoded for international/state sources missing or
    mismatched in the dataset
"""

import os
import pandas as pd
from datasets import load_dataset
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY"))

# ── Constants ─────────────────────────────────────────────────────────────────
DOMAINS = [
    "Middle East & Gulf",
    "US Politics & Foreign Policy",
    "Russia / Ukraine / NATO",
    "China / Taiwan / Indo-Pacific",
    "Global Economy & Trade Wars",
    "South Asia",
    "Africa & Resources",
    "Technology & AI Power",
    "Climate & Energy Transition",
]

FACTUAL_TO_WEIGHT = {
    "very high": 1.0,
    "high":      0.8,
    "mixed":     0.4,
    "low":       0.2,
    "very low":  0.1,
}

FACTUAL_TO_MBFC = {
    "very high": "Very High",
    "high":      "High",
    "mixed":     "Mixed",
    "low":       "Low",
    "very low":  "Low",
}

def placeholder(notes: str) -> dict:
    return {d: {"notes": notes, "status": "placeholder"} for d in DOMAINS}

def default_threshold() -> dict:
    return {d: "insufficient" for d in DOMAINS}


# ── Dataset sources ───────────────────────────────────────────────────────────
# Format: display_name -> domain (exact match in dataset)
DATASET_SOURCES = {
    # Wire services
    "Reuters":                  "reuters.com",
    "Associated Press":         "apnews.com",
    "AFP":                      "afp.com",
    # Western mainstream
    "BBC":                      "bbc.com",
    "New York Times":           "nytimes.com",
    "Financial Times":          "ft.com",
    "The Economist":            "economist.com",
    "Bloomberg":                "bloomberg.com",
    "NPR":                      "npr.org",
    "PBS":                      "pbs.org",
    "Axios":                    "axios.com",
    "Christian Science Monitor": "csmonitor.com",
    # Russia / Ukraine / NATO
    "Kyiv Independent":         "kyivindependent.com",
    "Euractiv":                 "euractiv.com",
    "Meduza":                   "meduza.io",
    # China / Indo-Pacific
    "Nikkei":                   "nikkei.com",
    "The Diplomat":             "thediplomat.com",
    "Asia Times":               "asiatimes.com",
    # Middle East
    "Haaretz":                  "haaretz.com",
    "Jerusalem Post":           "jpost.com",
    "Times of Israel":          "timesofisrael.com",
    # Africa
    "Daily Maverick":           "dailymaverick.co.za",
    "AllAfrica":                "allafrica.com",
    "Africa Check":             "africacheck.org",
    # Technology
    "Wired":                    "wired.com",
    "Ars Technica":             "arstechnica.com",
    "MIT Technology Review":    "technologyreview.com",
    # Climate
    "Carbon Brief":             "carbonbrief.org",
    "Climate Central":          "climatecentral.org",
}

# Notes per source for manual_bias_profiles
DATASET_SOURCE_NOTES = {
    "Reuters":                  "Wire service. Owned by Thomson Reuters. Corporate/Western financial establishment. Closest to neutral wire globally.",
    "Associated Press":         "Wire service. Non-profit cooperative. US institutional perspective baked in by default. Left-center per MBFC.",
    "AFP":                      "Wire service. French state-backed. Strong Africa and Francophone coverage. European perspective distinct from Anglo-American wire.",
    "BBC":                      "UK public broadcaster. Strong global reach. Pro-Western foreign policy consensus. Left-center per MBFC. Criticized on Israel/Palestine from both sides.",
    "New York Times":           "US. Liberal establishment. Strong investigative journalism. Significant influence on US foreign policy framing.",
    "Financial Times":          "UK. Global financial and business elite perspective. Excellent China and emerging market coverage. Establishment economic consensus.",
    "The Economist":            "UK. Liberal internationalist. Pro-globalization, pro-NATO. Influential among policy elites worldwide.",
    "Bloomberg":                "US. Financial and business elite. Strong economics, commodities, emerging markets. Left-center per MBFC.",
    "NPR":                      "US public broadcaster. Left-center per MBFC. Strong domestic US coverage. Credible international reporting.",
    "PBS":                      "US public broadcaster. Left-center per MBFC. Credible, low-sensationalism reporting.",
    "Axios":                    "US digital native. Left-center per MBFC. Strong on US politics and policy. Concise format.",
    "Christian Science Monitor": "US. Neutral per MBFC. Global coverage with low bias. Nonprofit. Underrated source for international stories.",
    "Kyiv Independent":         "Ukraine. Left-center per MBFC. Essential Ukrainian perspective on Russia/Ukraine conflict. Founded by journalists who left Kyiv Post.",
    "Euractiv":                 "EU. Left-center per MBFC. Essential for EU policy, NATO, and European perspectives on Russia/Ukraine.",
    "Meduza":                   "Russia — independent, exile-based. Left per MBFC. Critical counterweight to RT/TASS. Reports on Russia without state control.",
    "Nikkei":                   "Japan. Right-center per MBFC. Strong China, Southeast Asia, and technology coverage. Asian financial perspective.",
    "The Diplomat":             "Indo-Pacific specialist. Neutral per MBFC. Strong on ASEAN, Taiwan, South China Sea, regional security.",
    "Asia Times":               "Asia. Neutral per MBFC. Broad Asia-Pacific coverage. Useful for non-Western perspective on Indo-Pacific.",
    "Haaretz":                  "Israel. Left per MBFC. Left-leaning Israeli perspective. Critical of Israeli government. Important counterweight to state-aligned Israeli sources.",
    "Jerusalem Post":           "Israel. Right-center per MBFC. Right-leaning Israeli perspective. Closer to Israeli government and military framing.",
    "Times of Israel":          "Israel. Left-center per MBFC. Center-ground Israeli English-language outlet. Strong on Israeli domestic politics.",
    "Daily Maverick":           "South Africa. Neutral per MBFC. Best investigative outlet on African continent. Strong on Southern and East Africa, resources, governance.",
    "AllAfrica":                "Africa. Neutral per MBFC. Aggregates news from across the African continent. Essential for pan-African coverage.",
    "Africa Check":             "Africa. Neutral per MBFC. African fact-checking organization. Credibility signal for African stories.",
    "Wired":                    "US. Left-center per MBFC. Strong technology, AI, cybersecurity coverage. Essential for Technology & AI Power domain.",
    "Ars Technica":             "US. Neutral per MBFC. Deep technical coverage. Strong on semiconductors, AI, and cybersecurity.",
    "MIT Technology Review":    "US. Neutral per MBFC. Academic-adjacent. Strong on AI policy, emerging tech, and geopolitics of technology.",
    "Carbon Brief":             "UK. Left-center per MBFC. Climate science specialist. Essential for Climate & Energy domain. Data-driven.",
    "Climate Central":          "US. Neutral per MBFC. Climate science organization. Credible quantitative climate analysis.",
}

# ── Manual sources ────────────────────────────────────────────────────────────
# Sources missing from dataset, mismatched, or state media included deliberately
MANUAL_SOURCES = [
    {
        "name": "Al Jazeera",
        "status": "active",
        "mbfc_credibility": "Mixed",
        "credibility_weight": 0.4,
        "manual_bias_profiles": placeholder(
            "Qatar state-funded. Qatari foreign policy interests. Exceptional Middle East "
            "and Gaza coverage. Strong Global South voice. Anti-Saudi, pro-Muslim Brotherhood "
            "adjacent. Mixed per MBFC due to uncorrected fact checks. Framing is primary signal."
        ),
        "pattern_threshold": default_threshold(),
        "_source": "manual",
    },
    {
        "name": "RT",
        "status": "active",
        "mbfc_credibility": "Low",
        "credibility_weight": 0.2,
        "manual_bias_profiles": placeholder(
            "Russian state media. Primary vehicle for Russian government framing. Low factual "
            "credibility. Value is as explicit state narrative source — framing is the signal, "
            "not the facts. Confidence weighting handles low credibility."
        ),
        "pattern_threshold": default_threshold(),
        "_source": "manual",
    },
    {
        "name": "CGTN",
        "status": "active",
        "mbfc_credibility": "Mixed",
        "credibility_weight": 0.4,
        "manual_bias_profiles": placeholder(
            "Chinese state media (CCTV). Primary vehicle for CCP framing. Mixed per MBFC, "
            "LOW credibility overall. Reveals Chinese government narrative on Taiwan, South "
            "China Sea, Belt & Road. Framing is the signal."
        ),
        "pattern_threshold": default_threshold(),
        "_source": "manual",
    },
    {
        "name": "Dawn",
        "status": "active",
        "mbfc_credibility": "Mixed",
        "credibility_weight": 0.4,
        "manual_bias_profiles": placeholder(
            "Pakistan's leading English daily. Left-center per MBFC. Essential for Pakistani "
            "state and military perspective. Key counterweight to Indian sources on South Asia."
        ),
        "pattern_threshold": default_threshold(),
        "_source": "manual",
    },
    {
        "name": "The Hindu",
        "status": "active",
        "mbfc_credibility": "High",
        "credibility_weight": 0.8,
        "manual_bias_profiles": placeholder(
            "India. Progressive and secular Indian perspective. Strong foreign policy coverage. "
            "Dataset matched wrong domain (business line) — manually added. Left-center "
            "editorially. Important counterweight to Indian nationalist framing."
        ),
        "pattern_threshold": default_threshold(),
        "_source": "manual",
    },
    {
        "name": "Times of India",
        "status": "active",
        "mbfc_credibility": "High",
        "credibility_weight": 0.8,
        "manual_bias_profiles": placeholder(
            "India's largest English daily. Indian nationalist perspective. Key for South Asia, "
            "India-China, India-Pakistan coverage. Not in MBFC dataset — manually added."
        ),
        "pattern_threshold": default_threshold(),
        "_source": "manual",
    },
    {
        "name": "South China Morning Post",
        "status": "active",
        "mbfc_credibility": "High",
        "credibility_weight": 0.8,
        "manual_bias_profiles": placeholder(
            "Hong Kong, owned by Alibaba. Covers China with more depth than Western outlets. "
            "Not pure CCP line but influenced by Alibaba ownership. Essential for China/HK "
            "coverage distinct from CGTN. Not cleanly in MBFC dataset — manually added."
        ),
        "pattern_threshold": default_threshold(),
        "_source": "manual",
    },
    {
        "name": "Arab News",
        "status": "active",
        "mbfc_credibility": "Mixed",
        "credibility_weight": 0.4,
        "manual_bias_profiles": placeholder(
            "Saudi Arabia. Saudi state-adjacent. Primary vehicle for Saudi perspective on Iran, "
            "Yemen, Qatar. Essential for Middle East & Gulf agenda spectrum. Not in dataset — "
            "manually added."
        ),
        "pattern_threshold": default_threshold(),
        "_source": "manual",
    },
]


# ── Seed logic ────────────────────────────────────────────────────────────────
def load_mbfc_dataset() -> pd.DataFrame:
    print("Loading Idiap MBFC dataset from HuggingFace...")
    ds = load_dataset("sergioburdisso/news_media_bias_and_factuality", split="train")
    df = pd.DataFrame(ds)
    print(f"  {len(df)} sources loaded\n")
    return df


def build_dataset_records(df: pd.DataFrame) -> list[dict]:
    records = []
    for name, domain in DATASET_SOURCES.items():
        row = df[df["source"] == domain]
        if row.empty:
            print(f"  ⚠️  Not found in dataset: {name} ({domain}) — skipping")
            continue

        row = row.iloc[0]
        factual = str(row.get("factual_reporting", "mixed")).lower().strip()
        weight = FACTUAL_TO_WEIGHT.get(factual, 0.4)
        mbfc = FACTUAL_TO_MBFC.get(factual, "Mixed")
        notes = DATASET_SOURCE_NOTES.get(name, f"Source: {domain}")

        records.append({
            "name": name,
            "status": "active",
            "mbfc_credibility": mbfc,
            "credibility_weight": weight,
            "manual_bias_profiles": placeholder(notes),
            "pattern_threshold": default_threshold(),
            "_source": "dataset",
        })
    return records


def seed():
    df = load_mbfc_dataset()
    dataset_records = build_dataset_records(df)
    all_records = dataset_records + MANUAL_SOURCES

    print(f"Seeding {len(all_records)} sources "
          f"({len(dataset_records)} from dataset, {len(MANUAL_SOURCES)} manual)...\n")

    success, failed = 0, 0
    for record in all_records:
        source = record["_source"]
        # Remove internal field before upserting
        db_record = {k: v for k, v in record.items() if k != "_source"}
        try:
            sb.table("source_profiles").upsert(
                db_record, on_conflict="name"
            ).execute()
            print(f"  ✅ [{source:>7}] {db_record['name']:<35} "
                  f"{db_record['mbfc_credibility']:<10} {db_record['credibility_weight']}")
            success += 1
        except Exception as e:
            print(f"  ❌ [{source:>7}] {db_record['name']}: {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"✅ Seeded: {success}  ❌ Failed: {failed}")
    print(f"  {len(dataset_records)} from Idiap MBFC dataset")
    print(f"  {len(MANUAL_SOURCES)} manually hardcoded")


if __name__ == "__main__":
    seed()