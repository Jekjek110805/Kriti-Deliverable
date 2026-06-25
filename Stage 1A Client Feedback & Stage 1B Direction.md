
## Overview

Following the Stage 1A demonstration, Kriti provided feedback on how the opportunity analysis should evolve. The feedback indicates that the next stage should move beyond simply identifying opportunities and instead help determine **where each keyword should be implemented** within the website.

This keeps the workflow focused on SEO strategy before progressing to content creation.

---

# Key Feedback

## 1. Not Every Opportunity Requires Action

Some existing pages already satisfy the target keyword and do not require further optimization.

**Example:**

- Removal Reviews → No changes required.
    

### Stage 1B Requirement

The system should be able to recommend:

- No Change
    
- Improve Existing Page
    
- Create New Content
    

instead of always recommending an optimization or new page.

---

## 2. Identify the Correct Content Type

For keywords that require new content, the system should determine the most appropriate page type.

Instead of simply recommending:

> Create New Content

the system should specify whether the keyword belongs in:

- Existing Blog
    
- Existing Landing Page
    
- New Blog
    
- New Landing Page
    

Example:

|Keyword|Recommendation|
|---|---|
|House removal costs|New Blog|
|Moving company London|Existing Landing Page|

---

## 3. Determine Where Keywords Should Be Implemented

The next capability should answer:

> **Where should this keyword live?**

For every opportunity, the AI should determine whether:

- an existing page already satisfies the intent,
    
- an existing page should be optimized,
    
- or a completely new page should be created.
    

---

## 4. Continue Keyword Gap Analysis

Alongside evaluating existing pages, the workflow should also perform keyword gap analysis.

The system should identify:

- keywords currently not covered,
    
- opportunities competitors are targeting,
    
- missing topical coverage,
    
- content gaps that require new pages.
    

This analysis should run alongside the existing-page evaluation rather than as a separate process.

---

## 5. Provide AI-Powered SEO Recommendations

For each keyword, the AI should provide a clear implementation recommendation, including:

- Recommended action
    
- Target page (if one exists)
    
- Suggested content type
    
- Reasoning behind the recommendation
    
- Confidence level
    

Example:

**Keyword**  
House removal costs

**Recommendation**  
Create New Blog

**Reason**

- No existing page fully satisfies search intent.
    
- Strong informational intent.
    
- Better suited as an evergreen blog article.
    

**Confidence**  
92%

---

# Proposed Stage 1B Workflow

```text
Google Search Console Data
            ↓
Opportunity Detection
            ↓
Existing Page Evaluation
            ↓
Keyword Gap Analysis
            ↓
Implementation Recommendation
            ↓
Determine Content Type
(Blog or Landing Page)
            ↓
Approval Queue
```

---

# Expected Stage 1B Output

Each opportunity should include:

|Field|Description|
|---|---|
|Keyword|Target search query|
|Existing Page|Matching page (if available)|
|Recommendation|No Change / Improve Existing / Create New|
|Content Type|Blog / Landing Page|
|Reason|Why the recommendation was made|
|Confidence|AI confidence score|
|Next Action|Ready for approval|

---

# Stage 1B Business Outcome

Instead of only identifying SEO opportunities, the platform will help answer:

- Which keywords require no action?
    
- Which keywords belong on existing pages?
    
- Which keywords require entirely new content?
    
- Should that content be a blog or a landing page?
    
- Why is this the recommended approach?
    

This provides a clear SEO implementation strategy before progressing to content planning and content generation.