# NewsGT — Architecture

## Overview

NewsGT is built as a multi-layer analysis pipeline. Each layer answers a distinct question about a news event, building on the output of the layer below it.

---

## The 5 Layers

**Layer 1 — WHAT**
Determines what actually happened. Coverage of the same event is collected from sources across the ideological and geographic spectrum. Factual claims are extracted and cross-referenced to produce a verified event sequence. Divergences between sources are surfaced as framing signals.

**Layer 2 — WHO**
Identifies the declared actors involved. Each actor is documented with their stated position and verifiable interests. No inference beyond publicly established facts.

**Layer 3 — HOW**
Analyzes the operational mechanics of each actor — what levers they are pulling and what constraints they are operating under. Financial and economic signals are injected as grounding data.

**Layer 4 — WHY**
Examines the deep motivations driving each actor's behavior — structural forces, ideological commitments, and material interests. Every analytical claim carries a confidence label: ESTABLISHED, PROBABLE, ASSESSED, or SPECULATIVE.

**Layer 5 — WHAT NEXT** *(in development)*
Predictions. Deferred to a future phase.

---

## Source Universe

NewsGT maintains a curated universe of 37 credibility-verified sources spanning wire services, national broadcasters, regional press, specialist outlets, and state media across 9 geopolitical domains.

Sources are selected for geographic and ideological diversity — not neutrality. A source's agenda on a specific topic is itself a signal.

Credibility ratings are derived from the [Idiap Research Institute MBFC dataset](https://huggingface.co/datasets/sergioburdisso/news_media_bias_and_factuality) (Apache 2.0).

---

## The 9 Domains

1. Middle East & Gulf
2. US Politics & Foreign Policy
3. Russia / Ukraine / NATO
4. China / Taiwan / Indo-Pacific
5. Global Economy & Trade Wars
6. South Asia
7. Africa & Resources
8. Technology & AI Power
9. Climate & Energy Transition

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| News ingestion | GDELT DOC 2.0 API |
| Source credibility | Idiap/MBFC dataset (HuggingFace) |
| NLP extraction | spaCy, Gemini 2.5 Flash |
| Analysis reasoning | Claude Sonnet API |
| Financial data | FRED, yfinance, World Bank, IMF |
| Database | PostgreSQL (Supabase) |
| Cache | Redis (Upstash) |
| Frontend | Next.js |
| Deployment | Vercel, Railway |

---

## Design Principles

- **Behavioral over static** — source bias is measured per story, not assigned as a fixed label
- **Intersection over union** — facts confirmed across ideologically opposed sources carry more weight
- **Confidence labeling throughout** — no claim is made without stating how well it is supported
- **No hidden actors** — analysis is grounded in documented, publicly verifiable facts only