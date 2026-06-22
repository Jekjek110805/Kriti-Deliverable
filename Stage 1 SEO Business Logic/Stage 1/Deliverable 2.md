
# Monthly Opportunity Report Framework v2

## Purpose

Provide a standardized output format for Stage 1 research.

This report becomes the primary deliverable provided to Kriti each month and serves as the input for:

- Topic Approval
    
- Content Calendar Planning
    
- Stage 2 Brief Generation
    
- Existing Page Optimization Decisions
    

The report consolidates:

- SEMrush opportunities
    
- GSC opportunities
    
- Audience research
    
- Existing-page analysis
    
- Opportunity scoring
    
- Final recommendations
    

This directly supports Phase 0 and Phase 1 of Kriti's SOP.

---

# Stage 1 Workflow Context

```mermaid
flowchart LR

A[Topic Discovery]
--> B[GSC Analysis]

B --> C[Keyword Validation]

C --> D[Audience Research]

D --> E[Opportunity Scoring]

E --> F[Monthly Opportunity Report]

F --> G[Human Approval]
```

---

# Report Structure

The Monthly Opportunity Report contains 5 sections:

|Section|Purpose|
|---|---|
|Executive Summary|Quick leadership overview|
|Existing Page Opportunities|Highest-priority recommendations|
|New Content Opportunities|New content recommendations|
|Audience Insights|Questions and content ideas|
|Approval Queue|Topics requiring approval|

---

# Section 1 — Executive Summary

## Purpose

Allow stakeholders to understand monthly opportunities in under 5 minutes.

### Output Example

```text
Month: July 2026

Total Opportunities: 24

Existing Page Opportunities: 14

New Content Opportunities: 10

Critical Priority: 6

High Priority: 8

Medium Priority: 7

Low Priority: 3

Top Opportunity:
Improve Existing Page:
"CRM Software for Clinics"

Current Position: 8
Volume: 400
Expected Impact: High
```

---

# Section 2 — Existing Page Opportunities

## Purpose

Support Kriti's highest-priority SOP rule:

> Improve existing pages before creating new URLs.

### Report Format

|Keyword|URL|Position|Impressions|Volume|KD|Opportunity Score|Recommendation|
|---|---|---|---|---|---|---|---|
|CRM for Clinics|/crm-clinics|8|2,100|400|22|92|Improve Existing|
|CRM Comparison|/crm-guide|14|1,500|1200|35|84|Expand Existing|

---

## Required Supporting Notes

For each recommendation:

```text
Current Ranking Page

Intent Match

Improvement Opportunity

Suggested Sections

Potential Internal Links

Expected Impact
```

---

# Section 3 — New Content Opportunities

## Purpose

Identify opportunities where no existing page can reasonably satisfy search intent.

### Report Format

|Keyword|Volume|KD|Intent|Audience|Score|Recommendation|
|---|---|---|---|---|---|---|
|Best CRM for Clinics|600|28|BOFU|Clinic Owners|89|New Content|
|Clinic CRM Pricing|300|20|BOFU|Decision Makers|83|New Content|

---

## Required Supporting Notes

```text
Why Existing Pages Cannot Win

Target Audience

Business Value

Suggested Content Angle

Suggested CTA
```

---

# Section 4 — Audience Insights

## Purpose

Capture real user questions.

Source requirements come directly from the SOP:

- Reddit
    
- Quora
    
- People Also Ask
    
- Answer The Public
    

---

## Report Format

### Topic

CRM Software for Clinics

### Questions Found

|Source|Question|
|---|---|
|Reddit|What CRM works best for small clinics?|
|Reddit|How do clinics manage patient follow-ups?|
|Quora|Is CRM worth it for healthcare practices?|
|PAA|What CRM do medical clinics use?|

---

## Suggested H2 Opportunities

```text
Best CRM Features for Clinics

How Clinics Use CRM Systems

Choosing CRM for Small Practices

CRM Cost Considerations
```

---

# Section 5 — Approval Queue

## Purpose

Support Human-In-The-Loop governance.

Nothing progresses to Stage 2 until approved.

---

## Approval Table

|Topic|Recommendation|Priority|Reviewer|Status|
|---|---|---|---|---|
|CRM for Clinics|Improve Existing|Critical|TBD|Pending|
|Best CRM for Clinics|New Content|High|TBD|Pending|

---

## Approval Options

```text
Approved

Approved with Notes

Rejected

Needs Further Research
```

---

# Opportunity Recommendation Logic

## Rule 1

If:

```text
Existing Page Score >= 15
```

Then:

```text
Recommendation = Improve Existing Page
```

---

## Rule 2

If:

```text
No Suitable Existing Page
```

Then:

```text
Recommendation = Create New Content
```

---

## Rule 3

If:

```text
Intent = TOFU
AND
No Conversion Path
```

Then:

```text
Reject Opportunity
```

This follows Kriti's SOP requirement that content should target buyers, users, or warm leads rather than pure traffic.

---

# Content Calendar Export Format

Approved opportunities must be exportable into the content calendar.

|Field|Value|
|---|---|
|Topic||
|Keyword||
|Opportunity Type||
|Volume||
|KD||
|Intent||
|Existing Page URL||
|Current Position||
|Priority||
|Recommendation||
|Approval Status||

---

# Agent Responsibilities

|Agent|Contribution|
|---|---|
|Topic Discovery Agent|Initial opportunities|
|GSC Opportunity Agent|Ranking opportunities|
|Keyword Research Agent|Volume, KD, intent|
|Audience Research Agent|Reddit, Quora, PAA|
|Orchestrator Agent|Consolidation and report generation|

This aligns with the Stage 1 Research Layer architecture.

---

# Success Criteria

The Monthly Opportunity Report is complete when:

- All opportunities scored
    
- Existing-page evaluation completed
    
- GSC analysis completed
    
- Audience research attached
    
- Recommendations generated
    
- Approval queue generated
    
- Content calendar export prepared
    
- Human review ready
    

---

## Deliverable Output

At the end of Stage 1, the client can run:

```text
/monthly-topic-research
```

and receive:

```text
✓ Executive Summary

✓ Existing Page Opportunities

✓ New Content Opportunities

✓ Audience Insights

✓ Approval Queue

✓ Content Calendar Export
```

