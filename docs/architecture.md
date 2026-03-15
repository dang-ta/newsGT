# NewsGT — Architecture (Working Doc)
*Last updated: All open questions resolved except legal risk (parked) and λ (empirical)*

---

## Product Vision
Unbiased news and geopolitical analysis. Strip framing, surface facts, explain actor motivations through documented structural and ideological forces. Credible, transparent, non-conspiracy.

---

## Core Principle
**Dynamic bias calculation per event is the product.** Historical pattern is a small weighted input, not the foundation. The graph is a refinement of that input. Build the engine first. Layer depth as the product proves itself.

---

## The 5 Layers

### Layer 1 — WHAT
*What actually happened.*
- Collect coverage from credibility-verified source universe via GDELT
- Run dynamic bias analysis on each source for this specific story
- Extract factual claims using 5W1H (who, what, when, where, why, how) per article
- Build master fact set: union of all 5W1H extractions across all sources
- Intersection of claims across ideologically opposed sources = verified event sequence
- Apply confidence weighting formula to each claim
- Divergence between sources = framing/spin, flagged separately
- Story tracked over time via category_label — temporal evolution preserved
- **Output:** Clean chronological event sequence with confidence labels + "where sources diverge" section

### Layer 2 — WHO
*Who is involved.*
- Declared actors only — documented roles, observable interests
- No hidden actors, no inference beyond publicly established facts
- Agent-patient-verb role extraction across sources reveals how each outlet positions each actor
- **Output:** Actor map with roles and interests

### Layer 3 — HOW
*What each actor is actually doing.*
- Operational mechanics per actor
- Constraints: resources, alliances, domestic pressure, ideology
- Financial signals dynamically queried and injected (see Financial Data Layer)
- **Output:** Per-actor operational breakdown

### Layer 4 — WHY
*What each actor is ultimately optimizing for.*
- Three sub-lenses:
  - **Structural forces** — Turchin (elite overproduction, state fragility), Dalio (debt/empire cycles), Ibn Khaldun (asabiyyah) — grounded in live financial data
  - **Ideological scripts** — actors' own published doctrines, not inferred hidden beliefs
  - **Material interests** — follow the money, follow the power
- Confidence labeling on every claim: ESTABLISHED / PROBABLE / ASSESSED / SPECULATIVE
- Same confidence labels as claim intersection weighting — consistent throughout product
- **Output:** Per-actor motivation analysis across three sub-lenses

### Layer 5 — WHAT NEXT *(Phase 4)*
*Predictions. Deferred.*

---

## Bias Analysis Layer
*The core proprietary algo. Sits inside Layer 1. Informs all layers.*

### Design Principles
1. **Behavioral data is always primary.** Fresh analysis on every story — no free passes based on reputation
2. **Historical pattern is a small weighted prior, not a conclusion.** Never overrides fresh behavioral data
3. **Divergence is a signal.** Surfaced explicitly to the user when a source's behavior deviates from pattern
4. **No explicit event tracking.** Ownership changes and editorial shifts inferred from behavioral signal changes
5. **Output is always dual:** what this source did on this story + consistency with historical pattern

### The 5 Behavioral Signals
Derived independently for every source on every story:

1. **Selection** — did they cover it? How prominently? Absence from GDELT cluster is a data point
2. **Framing** — agent/patient/verb role assignment per actor. Who is cast as aggressor, victim, rational actor
3. **Omission** — what's in the master fact set but missing from this source
4. **Language** — word choice, emotional loading, labels ("terrorist" vs "militant", "invasion" vs "special operation")
5. **Sourcing** — whose voices are quoted, which sides are represented

### Historical Prior (small weighted input)
- **v1:** manual bias profiles per source per domain — 2-3 sentences documenting known tendencies, ownership, documented agenda
- **v2+:** automated from accumulated behavioral_records
- Weight in final output: minor. Fresh signals always dominate
- Pattern threshold: 3-5 stories in a domain = sufficient prior for that source

### Time-Weighting (historical prior only)
```
weight(record) = e^(-λt)
where t = age of record in months
      λ = tuned empirically in Phase 2 — cannot define upfront
```
Behavioral shift detection: significant divergence from decayed prior surfaced to user with date. No causal attribution — user investigates why.

### Source Status
Tracked as: `active / inactive / defunct`
No acquisition tracking — shifts inferred from behavioral data.

### Dynamic Bias Label Output (per source per story)
- What this source emphasized
- What this source omitted
- How this source positioned each actor
- Whether consistent with or diverging from historical pattern
- Example: *"On this story, Al Jazeera emphasizes civilian casualties and frames Actor X as aggressor — consistent with historical pattern on Middle East (17 prior stories). RT omits [fact Y] and frames Actor Z as provoked — consistent with historical pattern (9 prior stories)."*

---

## Intersection Confidence Weighting

### Formula
```
confidence(claim) = Σ credibility_weight(source_i) × D

where D = distinct agenda poles represented among agreeing sources
          ─────────────────────────────────────────────────────
          total agenda poles defined for this domain

credibility weights (from MBFC):
  Very High → 1.0
  High      → 0.8
  Mixed     → 0.4
  Low       → 0.2
```

### Confidence Labels
```
0.0 - 0.3 → SPECULATIVE
0.3 - 0.5 → ASSESSED
0.5 - 0.8 → PROBABLE
0.8 - 1.0 → ESTABLISHED
```
Same labels used consistently throughout all 5 layers.

### Examples
- RT + TASS + Press TV agreeing: 3 × 0.2 × low D = very low → SPECULATIVE
- Reuters + Al Jazeera + Times of India agreeing: 3 × 0.9 × high D = high → PROBABLE/ESTABLISHED
- Reuters + BBC + NYT agreeing: credible but low D (all Western) → ASSESSED despite high credibility

---

## Financial Data Layer
*Dynamic real-time injection into HOW and WHY layers.*

### Architecture
Two-step dynamic process per story:

**Step 1 — Metric identification (LLM)**
```
Given: story context + actor map from WHO layer
Output: 5-8 relevant financial metrics with:
  - What it measures
  - Which API provides it
  - Specific ticker or series ID
  - Why it's relevant to this story
```

**Step 2 — Dynamic query execution**
Identified metrics fetched in real time, formatted, injected as grounding data into HOW and WHY layer prompts.

### API Sources
| Source | Covers | Cost |
|--------|--------|------|
| **yfinance** | Stocks, ETFs, commodities, currencies, indices. Real-time + historical. Best for "follow the money" signals — defense stocks, oil prices, currency moves | Free |
| **FRED API** | 800K+ economic time series. GDP, inflation, debt ratios, wages, trade balances, money supply. Best for Turchin/Dalio structural metrics. Strong on US, partial on major economies | Free |
| **World Bank API** | Developing economies FRED misses. GDP per capita, Gini, debt, FDI flows for Nigeria, Pakistan, Congo etc. | Free |
| **IMF Data API** | Global. Government debt, current account balances, reserve currencies, exchange rates. Stronger than FRED on non-US | Free |
| **Alpha Vantage / Twelve Data** | Fills yfinance gaps on international equities and forex | Free tier |

### Gap Handling
When financial data unavailable for a specific actor (Russian oligarch assets, Chinese state enterprise internals, Gulf SWF positions, informal economy flows):
- Confidence label automatically downgrades to ASSESSED or SPECULATIVE
- Gap explicitly noted in output

---

## Category Graph
*Future refinement of historical prior. Not a v1 dependency.*

### Purpose
Transfers behavioral history across related domains when direct history is sparse. Built only after Phase 1 is live and behavioral records are accumulating.

### Design (when built)
- **Nodes:** topic category labels
- **Edges:** learned from behavioral data — cross-domain behavioral consistency
- **Edge weights:** recalculated quarterly
- **No manual weight definition** — fully learned from data

```
prior(source, X) =
  Σ history(source, Y) × edge_weight(X,Y) × recency_weight(Y)
  ─────────────────────────────────────────────────────────────
              Σ edge_weight(X,Y) × recency_weight(Y)
```

---

## Source Universe

### The 9 Domains
| # | Domain |
|---|--------|
| 1 | Middle East & Gulf |
| 2 | US Politics & Foreign Policy |
| 3 | Russia / Ukraine / NATO |
| 4 | China / Taiwan / Indo-Pacific |
| 5 | Global Economy & Trade Wars |
| 6 | South Asia |
| 7 | Africa & Resources |
| 8 | Technology & AI Power |
| 9 | Climate & Energy Transition |

### The 33 Sources (v1 universe)
**Wire services (credibility floor):**
Reuters, AP, AFP

**Western mainstream:**
BBC, The Guardian, Financial Times, The Economist, NYT, WSJ, Der Spiegel

**State / state-adjacent (explicit narrative sources — framing is the signal, not the facts):**
Al Jazeera, RT, CGTN/Xinhua, Press TV, TASS, France 24, DW

**Regional / non-Western:**
Times of India, The Hindu, Dawn, Haaretz, Jerusalem Post, Arab News, SCMP, Straits Times, Daily Maverick, Folha de S.Paulo

**Specialist / independent:**
Foreign Policy, The Intercept, Middle East Eye, Nikkei Asia, Bloomberg, The Wire (India)

### Domain × Agenda Poles
Each domain has defined agenda poles — used to calculate D in confidence weighting formula:

| Domain | Agenda Poles |
|--------|-------------|
| Middle East & Gulf | Western mainstream / Israeli / Arab state / Iranian / Russian / Independent |
| US Politics & Foreign Policy | US liberal establishment / US conservative / Adversarial left / Russian state / Chinese state / Non-Western |
| Russia / Ukraine / NATO | Russian state / Western mainstream / European / Global South |
| China / Taiwan / Indo-Pacific | CCP / HK-adjacent / Japanese / ASEAN / Western financial |
| Global Economy & Trade Wars | Financial West / US conservative / Japanese / Chinese state / Latin American |
| South Asia | Indian nationalist / Indian progressive / Pakistani / Independent Indian |
| Africa & Resources | African independent / French state / Chinese state / Western wire |
| Technology & AI Power | Financial West / Chinese state / Japanese / US conservative / Liberal internationalist |
| Climate & Energy | Progressive / Financial / French state / Qatari / Russian state / Latin American |

### Dynamic Source Selection (per story)
1. GDELT event cluster identifies which sources covered the story
2. Filter against universe — credibility-verified sources only
3. LLM assigns topic-relative agenda position for each source on this story

---

## True Build Order

### Phase 0 — Manual Foundation *(weeks)*
```
1. Write manual bias profiles: 33 sources × 9 domains
   → 2-3 sentences per source per domain
   → Known tendencies, ownership, documented agenda
   → This is the v1 historical prior

2. Build dynamic bias engine
   → 5 behavioral signals
   → 5W1H extraction (Gemini Flash + CoT)
   → Master fact set construction
   → Confidence weighting formula
   → Claim intersection + divergence mapping

3. Validate on known historical stories
   → Outputs match ground truth?
   → Bias labels coherent and defensible?
```

### Phase 1 — End-to-End Pipeline *(core product)*
```
1. GDELT ingestion → story clustering → source selection
2. Dynamic bias engine on live stories
3. Layer 1 (WHAT) → verified event sequence with confidence labels
4. Layer 2 (WHO) → actor map
5. Layer 3 (HOW) → operational breakdown + financial data injection
6. Layer 4 (WHY) → motivation analysis, structurally grounded
7. Output stored in PostgreSQL
8. Frontend in Next.js
```

### Phase 2 — Automated Historical Prior
```
1. behavioral_records accumulating from Phase 1
2. Automated pattern derivation replaces manual profiles
3. Exponential decay active, λ tuned empirically
4. Behavioral shift detection live
5. Manual profiles deprecated
```

### Phase 3 — Category Graph
```
1. Sufficient behavioral_records across multiple domains
2. Edge weights learned from cross-domain behavioral consistency
3. Graph traversal enriches prior for sparse categories
4. Quarterly recalculation
```

### Phase 4 — Predictions *(WHAT NEXT)*

---

## Tech Stack

### AI / LLM
| Need | Tool | Cost |
|------|------|------|
| Complex reasoning (HOW, WHY) | Claude Sonnet API | Paid, low volume |
| High-volume extraction (5W1H, bias signals, metric ID) | Gemini 2.5 Flash | Free tier |
| Self-hosted fallback | Llama 3.1 8B via Ollama | Free |

### News Ingestion
| Need | Tool | Cost |
|------|------|------|
| Global real-time + historical events | GDELT API | Free |
| RSS feeds | feedparser | Free |
| Non-English sources | GDELT Translingual (65 languages) | Free |

### Source Intelligence
| Need | Tool | Cost |
|------|------|------|
| Source credibility ratings | MBFC API | Free tier |
| Dynamic bias labeling | LLM + behavioral history | Free |

### NLP Pipeline
| Need | Tool | Cost |
|------|------|------|
| NER + coreference resolution | spaCy (en_core_web_trf) | Free |
| 5W1H extraction | Gemini Flash + Chain-of-Thought | Free tier |
| Agent-patient-verb triples | RELATIO or LLM | Free |
| Article deduplication | sentence-transformers | Free |
| Story clustering | GDELT event clusters | Free |

### Financial Data
| Need | Tool | Cost |
|------|------|------|
| Market signals | yfinance | Free |
| Macro/structural | FRED API | Free |
| Developing economies | World Bank API | Free |
| Global balances | IMF Data API | Free |
| Gaps | Alpha Vantage / Twelve Data | Free tier |

### Storage & Backend
| Need | Tool | Cost |
|------|------|------|
| All analysis + behavioral records | PostgreSQL (Supabase free tier) | Free |
| Category graph (Phase 3) | PostgreSQL recursive queries or Neo4j free | Free |
| Caching | Redis (Upstash free tier) | Free |
| Vector DB | Removed — RAG dropped | — |

### Frontend
| Need | Tool | Cost |
|------|------|------|
| Web app | Next.js → Vercel | Free tier |

---

## PostgreSQL Schema

### articles
*Raw ingested articles — input to everything downstream*
```
id
source_id             → source_profiles
story_id              → stories
gdelt_cluster_id
raw_text
url
published_at
language
processed             → boolean: has 5W1H extraction run?
```

### article_extractions
*Per-article 5W1H output before aggregation into master fact set*
```
id
article_id            → articles
source_id             → source_profiles
story_id              → stories
who                   → JSON: actors identified
what                  → text: action described
when                  → text or timestamp
where                 → text: location
why                   → text: stated reason
how                   → text: method/mechanism
raw_extraction        → JSON: full LLM output
master_version        → integer: which version of master_fact_set this was computed against
```

### stories
*One row per discrete story event. Related stories linked via thread_id*
```
id
gdelt_cluster_id
category_label        → one of 9 domains
headline
timestamp
master_fact_set       → JSON: union of all article_extractions
master_version        → integer: increments when new articles arrive and master is recomputed
master_frozen_at      → timestamp: when the 4-hour cutoff window closed
thread_id             → nullable: groups related stories on same ongoing event
thread_sequence       → integer: order within thread (1, 2, 3...)
is_thread_root        → boolean: true for first story in thread
```

### behavioral_records
*Per-source bias analysis output for each story*
```
id
source_id             → source_profiles
story_id              → stories
category_label        → one of 9 domains
timestamp
recency_weight        → e^(-λt), recalculated periodically
master_version        → integer: which master_fact_set version this was computed against
selection_score
omission_profile      → JSON: facts in master_fact_set absent from this source
framing_scores        → JSON: agent/patient/neutral per actor
language_tone         → JSON: sentiment per actor
sourcing_profile      → JSON: voices quoted, sides represented
divergence_flag       → boolean
divergence_detail     → text
```

### source_profiles
```
id
name
status                → active / inactive / defunct
mbfc_credibility      → Very High / High / Mixed / Low
credibility_weight    → 1.0 / 0.8 / 0.4 / 0.2
manual_bias_profiles  → JSON: domain → bias notes (v1 prior)
pattern_threshold     → JSON: domain → sufficient/forming/insufficient
```

### claims
*Each distinct verified fact from the master fact set, with confidence scoring*
```
id
story_id              → stories
claim_text
sources_reporting     → JSON: array of source_ids
source_agenda_positions → JSON: {source_id: agenda_pole} for sources_reporting
confidence_score      → float 0-1
confidence_label      → ESTABLISHED/PROBABLE/ASSESSED/SPECULATIVE
agenda_poles_covered  → JSON: distinct poles represented among agreeing sources
```

### financial_snapshots
*Financial metrics fetched dynamically per story for HOW/WHY grounding*
```
id
story_id              → stories
metric_name
metric_description
api_source            → FRED/yfinance/WorldBank/IMF/AlphaVantage
ticker_or_series_id
value
unit
timestamp_fetched
relevance_note        → why this metric matters for this story
available             → boolean: false triggers confidence downgrade in WHY layer
```

### layer_outputs
*Stored output of WHO, HOW, WHY layers per story*
```
id
story_id              → stories
layer                 → WHO/HOW/WHY
content               → JSON: full layer output
confidence_overall    → ESTABLISHED/PROBABLE/ASSESSED/SPECULATIVE
generated_at
model_used            → which LLM produced this
```

### category_edges *(Phase 3 only)*
```
node_a
node_b
weight
weight_history        → JSON
last_recalculated
```

---

## Pipeline Logic (non-schema decisions)

### Thread assignment
New story → LLM checks category_label + entity overlap + temporal proximity against existing threads → assigns thread_id if match found, creates new thread if not.

### Master fact set update window
- **4-hour cutoff** after first article in a cluster arrives
- Master fact set frozen at `master_frozen_at`
- All behavioral_records and claims computed after freeze
- `master_version` increments if late articles force a recompute
- behavioral_records store `master_version` they were computed against — staleness is trackable

---

## Parked
- **Publisher legal risk** — needs a position before public launch. Not blocking build.
- **λ tuning** — empirical, calibrated in Phase 2.