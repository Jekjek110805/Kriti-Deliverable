#!/usr/bin/env python3
"""Standalone Stage 1A analysis -- no yaml dependency, uses same logic as api.py"""
import csv, io, json, re, sys, os
from typing import Dict, List, Optional
from datetime import datetime

# ── Config ───────────────────────────────────────────────────────────────────

DEFAULT_MIN_IMPRESSIONS = 50
DEFAULT_MIN_POSITION = 3
DEFAULT_MAX_POSITION = 20

COLUMN_ALIASES = {
    "query": ["query", "keyword", "search_query"],
    "page": ["page", "url", "landing_page", "page_url"],
    "clicks": ["clicks"],
    "impressions": ["impressions"],
    "ctr": ["ctr", "click_through_rate"],
    "position": ["position", "avg_position", "average_position"],
}

BOFU_SIGNALS = [
    "best", "top", "software", "service", "provider", "pricing", "cost",
    "quote", "comparison", "compare", "versus", "vs", "alternative", "review",
    "near me", "for clinics", "for accountants", "for small business",
    "buy", "purchase", "demo", "trial", "free trial", "sign up", "signup",
]

MOFU_SIGNALS = [
    "how to choose", "how much does", "features", "benefits", "examples",
    "template", "checklist", "implementation", "mistakes", "guide", "tutorial",
    "how to", "what is", "tips", "strategies", "tools",
]

TOFU_SIGNALS = [
    "what is", "history of", "definition", "meaning", "why does",
    "basic explanation", "introduction", "overview",
]


def classify_intent(keyword: str) -> str:
    kw_lower = keyword.lower()
    for signal in BOFU_SIGNALS:
        if signal in kw_lower:
            return "BOFU"
    for signal in TOFU_SIGNALS:
        if signal in kw_lower:
            return "TOFU"
    for signal in MOFU_SIGNALS:
        if signal in kw_lower:
            return "MOFU"
    return "MOFU"


def rate_commercial_potential(keyword: str, intent: str, clicks: int) -> str:
    kw_lower = keyword.lower()
    buyer_words = ["buy", "pricing", "cost", "quote", "demo", "trial", "best", "top", "review", "software", "service"]
    if any(w in kw_lower for w in buyer_words) and intent == "BOFU":
        return "High"
    if intent == "BOFU":
        return "High"
    if intent == "MOFU" and clicks >= 50:
        return "High"
    if intent == "MOFU":
        return "Medium"
    return "Low"


def score_opportunity(row: Dict) -> Dict:
    position = row.get("position", 99)
    impressions = row.get("impressions", 0)
    intent = row.get("intent", "MOFU")
    commercial = row.get("commercial_potential", "Low")
    volume = row.get("volume", 0)
    if isinstance(volume, str) and volume == "not_available":
        volume = 0
    kd = row.get("keyword_difficulty", 50)
    if isinstance(kd, str) and kd == "not_available":
        kd = 50
    has_page = bool(row.get("page"))

    existing_page_score = 25 if has_page else 0

    if 3 <= position <= 5:
        position_score = 20
    elif 6 <= position <= 10:
        position_score = 18
    elif 11 <= position <= 20:
        position_score = 12
    else:
        position_score = 0

    if impressions >= 1000:
        impressions_score = 15
    elif impressions >= 500:
        impressions_score = 12
    elif impressions >= 200:
        impressions_score = 9
    elif impressions >= 50:
        impressions_score = 5
    else:
        impressions_score = 0

    if intent == "BOFU":
        intent_score = 20
    elif intent == "MOFU":
        intent_score = 14
    else:
        intent_score = 5

    if commercial == "High":
        commercial_score = 10
    elif commercial == "Medium":
        commercial_score = 6
    else:
        commercial_score = 2

    if kd > 0:
        if kd <= 20:
            kd_score = 10
        elif kd <= 35:
            kd_score = 8
        elif kd <= 50:
            kd_score = 5
        else:
            kd_score = 2
    else:
        kd_score = 0

    total = existing_page_score + position_score + impressions_score + intent_score + commercial_score + kd_score

    if total >= 80:
        priority = "Critical"
    elif total >= 65:
        priority = "High"
    elif total >= 50:
        priority = "Medium"
    else:
        priority = "Low"

    if has_page:
        if position <= 10 and intent in ("BOFU", "MOFU"):
            recommendation = "Improve Existing"
            reason = f"Page already ranks at position {position} with {intent} intent. Strong candidate for on-page optimization."
        elif position <= 20:
            recommendation = "Expand Existing"
            reason = f"Page ranks at position {position} but needs more content depth to compete for {intent} queries."
        else:
            recommendation = "Improve Existing"
            reason = f"Page exists but ranks outside page one. Needs significant improvement."
    else:
        recommendation = "Create New Content"
        reason = "No existing page found for this keyword. New content needed — defer to Stage 1C."

    return {
        "existing_page_score": existing_page_score,
        "position_score": position_score,
        "impressions_score": impressions_score,
        "intent_score": intent_score,
        "commercial_score": commercial_score,
        "kd_score": kd_score,
        "total_score": total,
        "priority": priority,
        "recommendation": recommendation,
        "reason": reason,
    }


def normalise_columns(rows: List[Dict]) -> List[Dict]:
    if not rows:
        return rows
    header_map = {}
    for col in rows[0].keys():
        col_lower = col.strip().lower()
        for canonical, aliases in COLUMN_ALIASES.items():
            if col_lower in aliases:
                header_map[col] = canonical
                break
        else:
            header_map[col] = col_lower

    normalised = []
    for row in rows:
        new_row = {}
        for orig, canon in header_map.items():
            new_row[canon] = row.get(orig, "").strip() if isinstance(row.get(orig), str) else row.get(orig, "")
        normalised.append(new_row)
    return normalised


def run_pipeline(rows, min_impressions=DEFAULT_MIN_IMPRESSIONS, min_position=DEFAULT_MIN_POSITION, max_position=DEFAULT_MAX_POSITION):
    rows = normalise_columns(rows)
    opportunities = []
    excluded = []

    for row in rows:
        query = row.get("query", "")
        page = row.get("page", "")
        try:
            position = int(row.get("position", 0) or 0)
        except (ValueError, TypeError):
            position = 0
        try:
            impressions = int(row.get("impressions", 0) or 0)
        except (ValueError, TypeError):
            impressions = 0
        try:
            clicks = int(row.get("clicks", 0) or 0)
        except (ValueError, TypeError):
            clicks = 0

        if not query or not page:
            excluded.append({"reason": "missing query or page", "row": query or "(empty)"})
            continue
        if position < min_position or position > max_position:
            excluded.append({"reason": f"position {position} outside {min_position}-{max_position}", "row": query})
            continue
        if impressions < min_impressions:
            excluded.append({"reason": f"impressions {impressions} below min {min_impressions}", "row": query})
            continue

        intent = classify_intent(query)
        commercial = rate_commercial_potential(query, intent, clicks)
        volume = "not_available"
        kd = "not_available"

        opp = {
            "keyword": query,
            "page": page,
            "position": position,
            "impressions": impressions,
            "clicks": clicks,
            "intent": intent,
            "commercial_potential": commercial,
            "volume": volume,
            "keyword_difficulty": kd,
        }

        scores = score_opportunity(opp)
        opp.update(scores)
        opp["approval_status"] = "needs_review"
        opportunities.append(opp)

    # Deduplicate by keyword (keep highest score)
    seen_keywords = {}
    deduped = []
    for opp in opportunities:
        kw = opp["keyword"].lower()
        if kw not in seen_keywords:
            seen_keywords[kw] = opp
            deduped.append(opp)
        else:
            excluded.append({
                "reason": f"duplicate keyword '{opp['keyword']}' — kept higher-scored entry",
                "row": opp["keyword"],
            })

    deduped.sort(key=lambda x: x["total_score"], reverse=True)
    return deduped, excluded


# ── Input data ───────────────────────────────────────────────────────────────

CSV_DATA = """query,page,clicks,impressions,ctr,position
clinic management software,/clinic-software,120,2450,4.9,8
ehr software,/ehr-guide,95,1800,5.2,6
patient management software,/patient-management,50,1400,3.5,14
medical billing software,/medical-billing,150,3100,4.8,5
telemedicine platform,/telemedicine-features,85,1950,4.3,9
healthcare crm,/healthcare-crm,40,1150,3.4,12
best clinic software,/clinic-software-comparison,180,4200,4.3,4
clinic scheduling software,/appointment-scheduling,70,1600,4.4,10
electronic medical records,/emr-guide,90,2100,4.2,7
patient engagement software,/patient-engagement,45,980,4.6,13
medical practice management,/practice-management,110,2800,3.9,11
ehr pricing,/ehr-pricing,60,950,6.3,3
crm for clinics,/healthcare-crm,55,1300,4.2,8
clinic crm software,/healthcare-crm,75,1750,4.3,6
telehealth software pricing,/telemedicine-pricing,35,820,4.1,15
medical software comparison,/software-comparison,95,2400,4.0,9
best emr software,/best-emr-software,160,3900,4.1,5
medical records management,/records-management,50,1250,4.0,12
healthcare software solutions,/healthcare-solutions,65,1450,4.5,10
ehr implementation guide,/ehr-implementation,40,900,4.4,16"""


def main():
    reader = csv.DictReader(io.StringIO(CSV_DATA))
    rows = list(reader)
    opportunities, excluded = run_pipeline(rows)

    W = 130
    print("=" * W)
    print(f"  STAGE 1A ANALYSIS RESULTS")
    print(f"  Input: {len(rows)} rows  |  Opportunities: {len(opportunities)}  |  Excluded: {len(excluded)}")
    print("=" * W)
    print()

    # Table
    print(f'  {"#":<4} {"Priority":<9} {"Keyword":<38} {"Pos":>4} {"Imp":>6} {"Clk":>5} {"Int":>5} {"Comm":>6} {"Score":>5} {"Recommendation":<18}')
    print("  " + "-" * 115)
    for i, o in enumerate(opportunities, 1):
        print(f'  {i:<4} {o["priority"]:<9} {o["keyword"]:<38} {o["position"]:>4} {o["impressions"]:>6} {o["clicks"]:>5} {o["intent"]:>5} {o["commercial_potential"]:>6} {o["total_score"]:>5} {o["recommendation"]:<18}')

    print()
    print("=" * W)
    print("  EXCLUSIONS")
    print("=" * W)
    if not excluded:
        print("  (none)")
    for e in excluded:
        print(f'  {e["row"]:<40} -- {e["reason"]}')

    print()
    print("=" * W)
    print("  BREAKDOWN BY RECOMMENDATION")
    print("=" * W)
    recs = {}
    for o in opportunities:
        r = o["recommendation"]
        recs[r] = recs.get(r, 0) + 1
    for r, c in sorted(recs.items(), key=lambda x: -x[1]):
        print(f'  {r:<20} {c}')

    print()
    print("=" * W)
    print("  BREAKDOWN BY INTENT")
    print("=" * W)
    intents = {}
    for o in opportunities:
        i = o["intent"]
        intents[i] = intents.get(i, 0) + 1
    for i, c in sorted(intents.items(), key=lambda x: -x[1]):
        print(f'  {i:<10} {c}')

    print()
    print("=" * W)
    print("  BREAKDOWN BY PRIORITY")
    print("=" * W)
    prios = {}
    for o in opportunities:
        p = o["priority"]
        prios[p] = prios.get(p, 0) + 1
    for p in ["Critical", "High", "Medium", "Low"]:
        if p in prios:
            print(f'  {p:<10} {prios[p]}')

    print()
    print("=" * W)
    print("  KEYWORD DEDUPLICATION (same keyword, different pages)")
    print("=" * W)
    kw_map = {}
    for o in opportunities:
        kw = o["keyword"].lower()
        if kw not in kw_map:
            kw_map[kw] = []
        kw_map[kw].append(o["page"])
    dedup_found = False
    for kw, pages in sorted(kw_map.items()):
        if len(pages) > 1:
            dedup_found = True
            print(f'  "{kw}" appears on pages: {pages}')
    if not dedup_found:
        print("  (no duplicate keywords across pages)")

    print()
    print("=" * W)
    print("  SAME PAGE, MULTIPLE KEYWORDS")
    print("=" * W)
    page_map = {}
    for o in opportunities:
        p = o["page"]
        if p not in page_map:
            page_map[p] = []
        page_map[p].append(o["keyword"])
    for p, kws in sorted(page_map.items(), key=lambda x: -len(x[1])):
        if len(kws) > 1:
            print(f'  {p}:')
            for kw in kws:
                print(f'    - {kw}')

    print()
    print("=" * W)
    print("  TOP 5 -- SCORE DETAIL")
    print("=" * W)
    for i, o in enumerate(opportunities[:5], 1):
        print(f'  #{i} "{o["keyword"]}" (score: {o["total_score"]}/100)')
        print(f'     Page: {o["page"]}  |  Position: {o["position"]}  |  Impressions: {o["impressions"]}  |  Clicks: {o["clicks"]}')
        print(f'     Intent: {o["intent"]}  |  Commercial: {o["commercial_potential"]}')
        print(f'     Scores: page={o["existing_page_score"]} pos={o["position_score"]} imp={o["impressions_score"]} int={o["intent_score"]} comm={o["commercial_score"]} kd={o["kd_score"]}')
        print(f'     Recommendation: {o["recommendation"]}')
        print(f'     Reason: {o["reason"]}')
        print()


if __name__ == "__main__":
    main()
