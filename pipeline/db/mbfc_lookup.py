"""
NewsGT — MBFC Lookup
Downloads the Idiap MBFC dataset from HuggingFace and looks up our 33 sources.
Prints what it finds so we can verify matches before seeding.
"""

import pandas as pd
from datasets import load_dataset

# ── Load dataset ──────────────────────────────────────────────────────────────
print("Loading MBFC dataset from HuggingFace...")
ds = load_dataset("sergioburdisso/news_media_bias_and_factuality", split="train")
df = pd.DataFrame(ds)
print(f"  Loaded {len(df)} sources")
print(f"  Columns: {list(df.columns)}\n")

# ── Our 33 sources — domain lookup map ───────────────────────────────────────
# Format: "display name" -> list of domains to try (in order)
SOURCES = {
    "Reuters":              ["reuters.com"],
    "Associated Press":     ["apnews.com", "ap.org"],
    "AFP":                  ["afp.com"],
    "BBC":                  ["bbc.com", "bbc.co.uk"],
    "The Guardian":         ["theguardian.com", "guardian.com"],
    "Financial Times":      ["ft.com"],
    "The Economist":        ["economist.com"],
    "New York Times":       ["nytimes.com"],
    "Wall Street Journal":  ["wsj.com"],
    "Der Spiegel":          ["spiegel.de"],
    "Al Jazeera":           ["aljazeera.com", "aljazeera.net"],
    "RT":                   ["rt.com"],
    "CGTN":                 ["cgtn.com"],
    "Press TV":             ["presstv.com", "presstv.ir"],
    "TASS":                 ["tass.com", "tass.ru"],
    "France 24":            ["france24.com"],
    "DW":                   ["dw.com"],
    "Times of India":       ["timesofindia.com", "timesofindia.indiatimes.com"],
    "The Hindu":            ["thehindu.com"],
    "Dawn":                 ["dawn.com"],
    "Haaretz":              ["haaretz.com"],
    "Jerusalem Post":       ["jpost.com"],
    "Arab News":            ["arabnews.com"],
    "South China Morning Post": ["scmp.com"],
    "Straits Times":        ["straitstimes.com"],
    "Daily Maverick":       ["dailymaverick.co.za"],
    "Folha de S.Paulo":     ["folha.uol.com.br", "folha.com.br"],
    "Foreign Policy":       ["foreignpolicy.com"],
    "The Intercept":        ["theintercept.com"],
    "Middle East Eye":      ["middleeasteye.net"],
    "Nikkei Asia":          ["asia.nikkei.com", "nikkei.com"],
    "Bloomberg":            ["bloomberg.com"],
    "The Wire India":       ["thewire.in"],
}

# ── Lookup ────────────────────────────────────────────────────────────────────
print(f"{'Source':<28} {'Domain':<30} {'Factual':<12} {'Credibility':<20} {'Bias'}")
print("-" * 110)

found, not_found = [], []

for name, domains in SOURCES.items():
    match = None
    matched_domain = None
    for domain in domains:
        # Try exact match first, then partial
        exact = df[df["source"] == domain]
        if not exact.empty:
            match = exact.iloc[0]
            matched_domain = domain
            break
        partial = df[df["source"].str.contains(domain.split(".")[0], case=False, na=False)]
        if not partial.empty:
            match = partial.iloc[0]
            matched_domain = match["source"]
            break

    if match is not None:
        factual = match.get("factual_reporting", "N/A")
        credibility = match.get("mbfc_credibility_rating", "N/A")
        bias = match.get("bias", "N/A")
        print(f"{name:<28} {matched_domain:<30} {str(factual):<12} {str(credibility):<20} {bias}")
        found.append(name)
    else:
        print(f"{name:<28} {'NOT FOUND':<30}")
        not_found.append(name)

print(f"\n✅ Found: {len(found)}/33")
if not_found:
    print(f"❌ Not found: {not_found}")
