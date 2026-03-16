"""
NewsGT — WHY Layer (v2)
Analyzes deep motivations per actor using evidence collected across all
prior pipeline steps. Reasons from behavioral evidence UP to motivations,
not from frameworks DOWN to predetermined conclusions.

Evidence sources:
  - behavioral_records: framing scores, omission profiles, language tone
  - claims: verified facts with confidence + source agreement
  - financial_snapshots: live market data
  - layer_outputs (WHO): actor map + cross-source framing
  - layer_outputs (HOW): operational levers + constraints

Frameworks applied as lenses to evidence:
  - Revealed preference: behavior reveals true priorities
  - Security dilemma: defensive actions appear offensive, explain escalation
  - Rentier state theory: resource-revenue states have specific political economy
  - Rally around the flag: external conflict used to boost internal legitimacy
  - Credible commitment problem: explains why negotiation fails
  - Turchin structural-demographic: elite overproduction, state fragility
  - Dalio empire/debt cycles: reserve currency, wealth gaps
  - Ibn Khaldun asabiyyah: social cohesion, group solidarity
  - Eschatological scripts: ideological end-states driving behavior
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

GROQ_MODEL    = "llama-3.3-70b-versatile"
REQUEST_DELAY = 1.0

# ── WHY prompt ────────────────────────────────────────────────────────────────
WHY_PROMPT = """You are a geopolitical deep motivation analysis engine.

You reason from EVIDENCE UP to motivations. Not from frameworks DOWN to conclusions.

REASONING CHAIN (follow exactly):
1. Scan ALL behavioral evidence provided
2. Identify the 3-5 SHARPEST signals — the most specific, most divergent, most revealing
3. For each sharp signal, name the exact source and quote the exact behavior
4. Select the framework that best explains WHY that specific behavior occurred
5. State a falsifiable conclusion tied to that specific evidence

WHAT COUNTS AS A SHARP SIGNAL:
- A source using loaded language that reveals editorial positioning (e.g. "relentlessly bombing", "deception and trickery", "fighting for survival")
- An actor framed as AGENT by some sources and PATIENT by others on the same action
- A fact present in the master set but absent from a specific source's coverage
- A financial metric that directly constrains an actor's options
- A behavioral gap between what an actor says and what they do

CITATION RULES — non-negotiable:
- Every claim MUST name the specific source: "[Dawn]", "[Tribune.com.pk]", "[Jerusalem Post]"
- Every language signal MUST quote the exact term used: "Dawn uses 'relentlessly bombing' to describe US action"
- Every framing signal MUST state the role: "[CBS News] frames Iran as PATIENT receiving strikes, [Dawn] frames Iran as AGENT fighting for survival"
- Every financial signal MUST state the number: "Iranian Rial at 0.0 USD indicates currency collapse"
- NO generic summaries. NO "sources indicate". NO "according to the evidence"

AVAILABLE FRAMEWORKS (apply as lenses to specific evidence only):
- Revealed preference: gap between stated position and observable behavior = true priority
- Security dilemma: defensive actions appear offensive, explain why de-escalation is hard
- Rentier state theory: resource-revenue states face existential pressure when revenue threatened
- Rally around the flag: leaders under domestic pressure escalate external conflict for legitimacy
- Credible commitment problem: explains why negotiation fails even when actors want peace
- Turchin structural-demographic: elite overproduction, state fragility, intra-elite competition
- Dalio empire/debt cycles: reserve currency dynamics, imperial overextension
- Ibn Khaldun asabiyyah: declining social cohesion = increasing state fragility
- Eschatological scripts: ideological end-states prescribing behavior regardless of cost

CONFIDENCE LABELING — every claim:
ESTABLISHED: directly quoted from evidence provided
PROBABLE: supported by 2+ independent named sources
ASSESSED: reasoned inference from named evidence
SPECULATIVE: plausible but no direct evidence — must say so explicitly

EXAMPLE OUTPUT STRUCTURE (follow this exactly):
{
  "actor_motivations": [
    {
      "actor": "Iran",
      "sharp_signals": [
        {
          "signal_type": "language",
          "source": "Dawn",
          "observation": "Dawn uses 'relentlessly bombing' to describe US action against Iran",
          "significance": "Reveals Dawn frames this as indiscriminate aggression, not targeted strikes"
        },
        {
          "signal_type": "framing",
          "source": "CBS News vs Dawn",
          "observation": "CBS News frames Iran as PATIENT receiving strikes; Dawn frames Iran as AGENT fighting for survival",
          "significance": "Same actor, opposite roles — Western vs Pakistani press divergence on who is aggressor"
        },
        {
          "signal_type": "financial",
          "source": "financial_snapshots",
          "observation": "Iranian Rial at 0.0 USD — effectively worthless against the dollar",
          "significance": "Currency collapse constrains Iran's ability to finance prolonged conflict"
        }
      ],
      "motivation_analysis": [
        {
          "framework": "Rentier state theory",
          "triggered_by": "Iranian Rial at 0.0 USD combined with Hormuz closure blocking oil exports",
          "conclusion": "Iran's Hormuz closure is an act of economic desperation — blocking others' oil because their own revenue is collapsing",
          "prediction": "Iran will maintain Hormuz threat as long as sanctions pressure continues — it is their only remaining leverage",
          "confidence": "PROBABLE"
        }
      ],
      "primary_motivation": "Iran is optimizing for regime survival under simultaneous external military pressure and internal economic collapse [Dawn: 'fighting for survival', Rial at 0.0]",
      "confidence_overall": "PROBABLE"
    }
  ]
}

Now analyze the actual evidence provided. Use this structure exactly.

{
  "actor_motivations": [
    {
      "actor": "string",
      "sharp_signals": [
        {
          "signal_type": "framing|omission|language|financial|behavioral_gap",
          "source": "string — exact source name",
          "observation": "string — exact quote or specific behavior observed",
          "significance": "string — what this reveals about motivation"
        }
      ],
      "motivation_analysis": [
        {
          "framework": "string — name of framework",
          "triggered_by": "string — exact signal that triggered this framework (name source + behavior)",
          "conclusion": "string — specific falsifiable motivation claim",
          "prediction": "string — what this framework predicts comes next",
          "confidence": "ESTABLISHED|PROBABLE|ASSESSED|SPECULATIVE"
        }
      ],
      "primary_motivation": "string — one sentence, must reference at least one specific signal",
      "confidence_overall": "ESTABLISHED|PROBABLE|ASSESSED|SPECULATIVE"
    }
  ],
  "synthesis": "string — 3 sentences max. Must cite at least 3 specific sources by name with specific observations.",
  "key_variable": "string — the single observable thing that confirms or breaks this analysis",
  "confidence_assessment": "string — overall level and what specific evidence would falsify it"
}"""


def build_evidence_package(story_id: str) -> dict:
    """
    Assemble the full evidence trail from all prior pipeline steps.
    This is what makes WHY trustworthy — it reasons from collected evidence.
    """
    evidence = {}

    # ── Behavioral records: framing, omissions, language per source ───────────
    behavioral = (
        sb.table("behavioral_records")
        .select("framing_scores, omission_profile, language_tone, "
                "sourcing_profile, divergence_flag, divergence_detail, "
                "source_profiles(name, credibility_weight)")
        .eq("story_id", story_id)
        .execute()
    ).data or []

    framing_signals   = []
    omission_signals  = []
    language_signals  = []
    sourcing_signals  = []
    divergence_flags  = []

    for rec in behavioral:
        source = (rec.get("source_profiles") or {}).get("name", "Unknown")
        cred   = (rec.get("source_profiles") or {}).get("credibility_weight", 0.4)

        # Framing per actor
        for actor in (rec.get("framing_scores") or {}).get("actors", []):
            framing_signals.append({
                "source":     source,
                "credibility": cred,
                "actor":      actor.get("name", ""),
                "role":       actor.get("role", ""),
                "verb":       actor.get("verb", ""),
                "note":       actor.get("framing_note", "")[:100],
            })

        # Omissions
        missing = (rec.get("omission_profile") or {}).get("missing_facts", [])
        if missing:
            omission_signals.append({
                "source":   source,
                "missing":  missing[:3],
                "pattern":  (rec.get("omission_profile") or {}).get("omission_notes", "")[:100],
            })

        # Language
        loaded = (rec.get("language_tone") or {}).get("loaded_terms", [])
        tone   = (rec.get("language_tone") or {}).get("overall_tone", "")
        if loaded or tone:
            language_signals.append({
                "source":       source,
                "loaded_terms": loaded[:3],
                "tone":         tone[:80],
            })

        # Sourcing gaps
        absent = (rec.get("sourcing_profile") or {}).get("sides_absent", [])
        if absent:
            sourcing_signals.append({
                "source":  source,
                "absent":  absent,
                "notes":   (rec.get("sourcing_profile") or {}).get("sourcing_notes", "")[:80],
            })

        # Divergences
        if rec.get("divergence_flag"):
            divergence_flags.append({
                "source": source,
                "detail": rec.get("divergence_detail", ""),
            })

    evidence["framing"]    = framing_signals
    evidence["omissions"]  = omission_signals
    evidence["language"]   = language_signals
    evidence["sourcing"]   = sourcing_signals
    evidence["divergences"]= divergence_flags

    # ── Claims: verified facts with confidence + source agreement ─────────────
    claims = (
        sb.table("claims")
        .select("claim_text, confidence_label, sources_reporting, "
                "agenda_poles_covered, confidence_score")
        .eq("story_id", story_id)
        .order("confidence_score", desc=True)
        .execute()
    ).data or []

    evidence["verified_claims"] = [
        {
            "claim":       c["claim_text"],
            "confidence":  c["confidence_label"],
            "score":       c["confidence_score"],
            "sources":     c["sources_reporting"],
            "poles":       c["agenda_poles_covered"],
        }
        for c in claims
    ]

    # ── Financial snapshots ───────────────────────────────────────────────────
    financials = (
        sb.table("financial_snapshots")
        .select("metric_name, value, unit, relevance_note, available")
        .eq("story_id", story_id)
        .execute()
    ).data or []

    evidence["financial"] = [
        {
            "metric":    f["metric_name"],
            "value":     f["value"] if f["available"] else "UNAVAILABLE",
            "unit":      f.get("unit", ""),
            "relevance": f.get("relevance_note", "")[:100],
            "available": f["available"],
        }
        for f in financials
    ]

    # ── WHO layer: actor map + cross-source framing ───────────────────────────
    who = (
        sb.table("layer_outputs")
        .select("content")
        .eq("story_id", story_id)
        .eq("layer", "WHO")
        .execute()
    ).data
    evidence["who"] = who[0]["content"] if who else {}

    # ── HOW layer: levers + constraints ──────────────────────────────────────
    how = (
        sb.table("layer_outputs")
        .select("content")
        .eq("story_id", story_id)
        .eq("layer", "HOW")
        .execute()
    ).data
    evidence["how"] = how[0]["content"] if how else {}

    return evidence


def build_why(story_id: str) -> dict:
    """Build WHY layer for a story using full evidence package."""

    story_result = (
        sb.table("stories")
        .select("id, category_label, master_fact_set, headline")
        .eq("id", story_id)
        .execute()
    )
    if not story_result.data:
        print(f"  Story not found: {story_id}")
        return {}

    story    = story_result.data[0]
    headline = (story.get("headline") or "")[:60]

    print(f"\n── WHY: {headline} ──")
    print(f"  Building evidence package...")

    # Assemble full evidence trail
    evidence = build_evidence_package(story_id)

    n_framing   = len(evidence.get("framing", []))
    n_omissions = len(evidence.get("omissions", []))
    n_claims    = len(evidence.get("verified_claims", []))
    n_financial = sum(1 for f in evidence.get("financial", []) if f["available"])
    print(f"  Evidence: {n_framing} framing signals, {n_omissions} omission profiles, "
          f"{n_claims} verified claims, {n_financial} live financial metrics")

    # Build prompt with full evidence
    prompt = f"""VERIFIED EVENT SEQUENCE:
{json.dumps(story.get('master_fact_set', {}).get('verified_sequence', []), indent=2)}

CATEGORY: {story['category_label']}

═══ BEHAVIORAL EVIDENCE ═══

FRAMING SIGNALS (how sources position each actor):
{json.dumps(evidence['framing'], indent=2)}

OMISSION PROFILES (what sources chose not to report):
{json.dumps(evidence['omissions'], indent=2)}

LANGUAGE SIGNALS (loaded terms and tone per source):
{json.dumps(evidence['language'], indent=2)}

SOURCING GAPS (whose voices are absent):
{json.dumps(evidence['sourcing'], indent=2)}

═══ VERIFIED CLAIMS (confidence-weighted) ═══
{json.dumps(evidence['verified_claims'], indent=2)}

═══ FINANCIAL SIGNALS ═══
{json.dumps(evidence['financial'], indent=2)}

═══ WHO LAYER (actor map + stated positions) ═══
{json.dumps(evidence['who'].get('actors', []), indent=2)}

═══ HOW LAYER (operational mechanics) ═══
{json.dumps(evidence['how'].get('actor_mechanics', []), indent=2)}

Now reason from this evidence to deep motivations. 
Cite specific evidence for every claim. Return only valid JSON."""

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": WHY_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.0,
            max_tokens=5000,
        )

        raw = response.choices[0].message.content.strip()

        if "```" in raw:
            parts = raw.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    raw = part
                    break

        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start == -1 or end == 0:
            print("  ⚠️  No JSON in WHY response")
            return {}

        result = json.loads(raw[start:end])

    except Exception as e:
        print(f"  ⚠️  WHY LLM error: {e}")
        return {}

    # Overall confidence
    conf_labels = []
    for m in result.get("actor_motivations", []):
        conf_labels.append(m.get("confidence_overall", "ASSESSED"))
        for fw in m.get("motivation_analysis", []):
            conf_labels.append(fw.get("confidence", "ASSESSED"))

    conf_order   = ["ESTABLISHED", "PROBABLE", "ASSESSED", "SPECULATIVE"]
    overall_conf = "ASSESSED"
    if conf_labels:
        counts       = {c: conf_labels.count(c) for c in conf_order}
        overall_conf = max(counts, key=counts.get)

    # Store
    sb.table("layer_outputs").insert({
        "story_id":          story_id,
        "layer":             "WHY",
        "content":           result,
        "confidence_overall":overall_conf,
        "model_used":        GROQ_MODEL,
    }).execute()

    # Print
    print(f"\n  SYNTHESIS:")
    print(f"  {result.get('synthesis', '')}")
    print(f"\n  KEY VARIABLE:")
    print(f"  {result.get('key_variable', '')}")
    print(f"\n  CONFIDENCE: {overall_conf}")
    print(f"  {result.get('confidence_assessment', '')}")
    print()

    for mot in result.get("actor_motivations", []):
        actor = mot.get("actor", "")
        print(f"  [{actor}] — {mot.get('primary_motivation', '')[:100]}")

        # Sharp signals
        for sig in mot.get("sharp_signals", [])[:3]:
            print(f"    [{sig.get('signal_type','?').upper()}] "
                  f"[{sig.get('source','')}] {sig.get('observation','')[:90]}")
            print(f"      → {sig.get('significance','')[:80]}")

        # Motivation analysis
        for fw in mot.get("motivation_analysis", [])[:2]:
            print(f"    [{fw.get('confidence','?')}] {fw.get('framework','')}")
            print(f"      Triggered by: {fw.get('triggered_by','')[:80]}")
            print(f"      Conclusion:   {fw.get('conclusion','')[:80]}")
            print(f"      Predicts:     {fw.get('prediction','')[:80]}")
        print()

    return result


def build_all_why() -> None:
    stories = sb.table("stories").select("id, headline").execute()
    for story in stories.data:
        build_why(story["id"])
        time.sleep(REQUEST_DELAY)


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if len(sys.argv) == 2:
        build_why(sys.argv[1])
    else:
        build_all_why()