    Hermes Plan for Kriti's Project  [[Kriri_Process_1]]
    ## Verdict

    **Yes, feasible. Mostly a neat fit.**  
    I would **not** position it as “Hermes fully runs Kriti’s blog production end-to-end.” I would position it as:

    > **Hermes runs the content operations system, enforces the SOP, prepares the work, catches failures, and hands humans only the decisions that genuinely need judgment.**

    That is a strong fit because Kriti’s process is already structured as a gated workflow: optimize existing pages before creating new ones, target buyers/users/warm leads rather than pure traffic, run monthly topic selection, then require every per-post phase to pass before publishing.

    The poor-fit version would be: **one autonomous agent researches, writes, sources images, uploads assets, publishes, requests indexing, and runs outreach without review.** That conflicts with the SOP’s own human-review requirement and creates avoidable risk around factual claims, permissions, logged-in tools, and publishing.

    ---

    ## Why Hermes is a good fit

    Hermes has the right primitives for this kind of recurring, tool-heavy workflow:

    |Need in Kriti’s process|Hermes feature fit|
    |---|---|
    |SOP enforcement|**Skills** can encode reusable workflows and checklist logic. Hermes skills are on-demand knowledge documents, with a clear `SKILL.md` structure for procedure, pitfalls, and verification. ([Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills "Skills System \| Hermes Agent"))|
    |Monthly recurring research|**Cron** can run one-shot or recurring tasks, attach one or more skills, and deliver results to chat, files, or platform targets. ([Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/features/cron "Scheduled Tasks (Cron) \| Hermes Agent"))|
    |GSC, SEMrush, calendar, CMS, site crawler integrations|**MCP** is the right layer for connecting Hermes to external APIs, internal services, databases, filesystems, and browser stacks, with per-server tool filtering. ([Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp/ "MCP (Model Context Protocol) \| Hermes Agent"))|
    |Logged-in UI-only work|**Browser automation** can navigate websites, fill forms, interact with page elements, extract information, and use screenshots/vision when text snapshots are insufficient. ([Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/features/browser/ "Browser Automation \| Hermes Agent"))|
    |Separate agents for research, QA, publishing|**Profiles** let you run multiple Hermes agents with separate config, API keys, memory, sessions, skills, cron jobs, and gateway state. ([Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/profiles/ "Profiles: Running Multiple Agents \| Hermes Agent"))|
    |Parallel research and QA|**Delegation** works for short-lived parallel tasks, while **Kanban** is better for durable human-in-the-loop workflows across named profiles. ([Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation "Subagent Delegation \| Hermes Agent")) ([Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban "Kanban (Multi-Agent Board) \| Hermes Agent"))|
    |Audit trail and blocking rules|**Hooks** can log agent activity, trigger alerts, intercept tool usage, and implement guardrails. ([Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks "Event Hooks \| Hermes Agent"))|

    The key is to use Hermes as a **workflow engine plus agent layer**, not just as a chatbot.

    ---

    ## Fit by SOP area

    |SOP area|Fit|Notes|
    |---|--:|---|
    |**Phase 1: monthly research and topic selection**|**Excellent**|This is one of the best fits. The agent can pull GSC query/page data, SEMrush metrics, SERP observations, Reddit/Quora-style questions, and produce a scored topic shortlist. Kriti’s SOP already expects a monthly locked list mapped to client and intent.|
    |**Phase 0: keyword and intent**|**Excellent**|A Hermes skill can force every candidate to include source, GSC position/impressions where available, intent, existing-page-vs-new-page decision, and calendar logging.|
    |**Existing page vs new URL decision**|**Excellent, if site crawl/CMS data is available**|The agent can crawl existing URLs, compare intent overlap, and recommend “improve existing” vs “create new.” This maps directly to Kriti’s rule against creating unnecessary new posts.|
    |**SEO structure, TLDR, metadata, heading hierarchy**|**Excellent**|Much of this can be checked deterministically: one H1, keyword in first paragraph, TLDR at top, title/meta/slug present, logical H2/H3 structure.|
    |**House style**|**Excellent**|No em dashes, no banned filler phrases, no competitor put-downs, short paragraphs, neutral comparison language. This is highly automatable with a mix of regex and LLM review.|
    |**Accuracy and hallucination check**|**Medium-high**|Hermes can produce a claim ledger, find source support, flag unsupported claims, and require citations. But the SOP explicitly requires a human to read the full post line by line, so final approval should stay human.|
    |**Media**|**Medium**|Hermes can define image needs, generate briefs, compress/rename images, write alt text, check dimensions, and prepare upload metadata. But “original photos” and logo permissions are not fully automatable.|
    |**Conversion checks**|**High**|CTA, next step, product/service links, and reader fit are easy to check and score.|
    |**Interlinking and indexing**|**Medium-high**|Internal link suggestions are a good fit. CMS edits can be automated if API access exists. GSC indexing is more delicate: Google’s Indexing API is officially limited to JobPosting and livestream-style BroadcastEvent pages, so normal blog indexing should be treated as a browser/manual Search Console step, not a clean API action. ([Google for Developers](https://developers.google.com/search/apis/indexing-api/v3/quickstart?utm_source=chatgpt.com "Indexing API Quickstart \| Google Search Central - Google Developers"))|
    |**AI search readiness**|**High**|Hermes can extract real audience questions, draft long natural-language H2s, and check that the TLDR gives a clean answer near the top.|
    |**Image backlink workflow**|**Medium-low for full automation**|Hermes can track originals, prepare upload metadata, run reverse image-search checks via browser, and draft outreach. I would keep upload/outreach approval human-controlled because platform rules, attribution, and permissions are brittle.|

    ---

    ## Recommended architecture

    ### Start with **one orchestrator profile**, then add specialist profiles

    I would not begin with a swarm. I would start with one hardened Hermes profile that proves the SOP can be enforced reliably, then split responsibilities once the workflow is stable.

    ### Profile 1: `kriti-content-ops`

    This is the main agent. It owns the SOP, the content calendar workflow, and the gate reports.

    **Core responsibilities:**

    - Run the monthly research workflow.
        
    - Create topic shortlists.
        
    - Decide “new post” vs “improve existing.”
        
    - Generate per-post briefs.
        
    - Run pre-publish gate checks.
        
    - Produce pass/fail reports.
        
    - Route tasks to humans or specialist agents.
        

    Do **not** store the SOP in Hermes memory. Hermes memory is intentionally bounded and curated, meant for preferences and compact operational facts. Put the SOP into a proper Hermes skill with reference files instead. Hermes memory is limited to small `MEMORY.md` and `USER.md` stores, while skills are the right place for procedural workflows. ([Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory "Persistent Memory | Hermes Agent")) ([Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills "Skills System | Hermes Agent"))

    ---

    ## Specialist agents I’d add after the MVP

    ### 1. `kriti-research-agent`

    **Purpose:** monthly topic discovery and opportunity scoring.

    **Tools/integrations:**

    - Google Search Console API
        
    - SEMrush API
        
    - Web search
        
    - Browser automation for SERP/manual checks
        
    - Reddit/Quora/public question mining
        
    - Content calendar write access
        

    Google’s Search Console API provides programmatic access to search performance reports, sitemaps, and related Search Console actions; the Search Analytics query endpoint supports custom filters and dimensions such as query and page, which maps well to the SOP’s “position 3 to 20 with impressions” requirement. ([Google for Developers](https://developers.google.com/webmaster-tools/?utm_source=chatgpt.com "Search Console API | Google for Developers")) ([Google for Developers](https://developers.google.com/webmaster-tools/v1/searchanalytics/query?utm_source=chatgpt.com "Search Analytics: query | Search Console API | Google for Developers")) Semrush’s API can provide keyword overview data including volume, CPC, competition, and keyword difficulty fields, which maps to Kriti’s volume/KD requirement. ([Semrush Developer](https://developer.semrush.com/api/seo/keyword-reports/?utm_source=chatgpt.com "Keyword reports | Semrush API"))

    **Output:**

    ```markdown
    Monthly Topic Shortlist

    Client:
    Topic:
    Target keyword:
    Source:
    GSC position:
    GSC impressions:
    SEMrush volume:
    SEMrush KD:
    Funnel stage:
    Existing page candidate:
    Recommendation: Improve existing / Create new
    Reason:
    Suggested H2s from public questions:
    ```

    ---

    ### 2. `kriti-brief-agent`

    **Purpose:** turn an approved topic into a content brief.

    **Responsibilities:**

    - Confirm intent.
        
    - Map audience and conversion goal.
        
    - Create H1/H2/H3 structure.
        
    - Draft TLDR requirements.
        
    - Draft page title, meta description, and URL slug.
        
    - Suggest CTA and internal links.
        
    - Specify image needs.
        
    - Identify required claims and source needs.
        

    This agent should not write the whole post by default. It should create a brief that a writer or writing system can use.

    ---

    ### 3. `kriti-gatekeeper-agent`

    **Purpose:** pre-publish QA.

    This is the most valuable agent in the setup.

    It should run the full Phase 0 and Phases 2 through 8 checklist and return:

    ```markdown
    Gate result: PASS / FAIL

    Blocking issues:
    1. Phase 4: Unsupported statistic in paragraph 7.
    2. Phase 3: Em dash found in H2.
    3. Phase 6: CTA is present but generic.

    Non-blocking improvements:
    1. Add a stronger product-service internal link.
    2. Rewrite FAQ answer to match user phrasing.

    Required human checks:
    1. Read full post line by line.
    2. Confirm logo permissions.
    3. Confirm all competitor descriptions are neutral.
    ```

    This agent should be **fail-closed**. If required data is missing, it fails the post rather than guessing.

    ---

    ### 4. `kriti-media-agent`

    **Purpose:** image preparation and backlink workflow support.

    **Good uses:**

    - Define hero and in-body image needs.
        
    - Generate Canva brief text.
        
    - Prepare filenames.
        
    - Compress/resize files.
        
    - Write alt text.
        
    - Track original image inventory.
        
    - Prepare upload descriptions and attribution text.
        
    - Draft outreach emails for missing attribution.
        

    **Keep human-controlled:**

    - Taking original photos.
        
    - Using recognizable logos.
        
    - Uploading to stock platforms.
        
    - Sending outreach emails.
        
    - Any claim that an image will “earn backlinks.”
        

    The SOP’s image-backlink idea is agent-assistable, but not something I would fully automate without review.

    ---

    ### 5. `kriti-publisher-agent`

    **Purpose:** CMS staging and post-publish checks.

    This should have the narrowest permissions.

    **Allowed:**

    - Create draft posts.
        
    - Populate metadata.
        
    - Add internal links.
        
    - Upload approved media.
        
    - Check sitemap inclusion.
        
    - Inspect index status.
        
    - Prepare Search Console steps.
        

    **Not allowed by default:**

    - Publish live pages without human approval.
        
    - Delete or overwrite existing posts.
        
    - Mass-edit site architecture.
        
    - Use Google Indexing API for ordinary blog posts.
        

    For regular blog content, I would use the agent to prepare the GSC indexing step or operate a logged-in browser only with explicit approval. Google’s official Indexing API is not a general blog-post submission API. ([Google for Developers](https://developers.google.com/search/apis/indexing-api/v3/quickstart?utm_source=chatgpt.com "Indexing API Quickstart | Google Search Central - Google Developers"))

    ---

    ## Use Kanban, not just subagents, for production

    Hermes has two relevant collaboration models:

    - **`delegate_task`**: good for short, parallel research jobs where the parent agent waits for the child’s result.
        
    - **Kanban**: better for durable workflows where humans and named agents need to inspect, comment, approve, retry, or pick up work later.
        

    For this client, I would use **Kanban as the production backbone**. Hermes Kanban is a durable task board shared across profiles, with tasks and handoffs stored in SQLite, and it is explicitly designed for workflows involving multiple named agents, retries, human input, and auditability. ([Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban "Kanban (Multi-Agent Board) | Hermes Agent"))

    A good task flow:

    ```text
    Research candidate
    → Human approves topic
    → Brief generated
    → Draft attached
    → Gatekeeper reviews
    → Human line edit
    → Media check
    → Publisher stages
    → Human approves publish
    → Post-publish indexing/internal-link check
    ```

    ---

    ## The core skills I’d create

    I would package this as a Hermes profile distribution once stable, because Hermes supports distributing a complete profile with personality, skills, cron jobs, MCP connections, and config as a git repo. ([Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/profile-distributions "Profile Distributions: Share a Whole Agent | Hermes Agent"))

    ### Skill bundle: `/maai-blog-gate`

    Contains:

    1. `keyword-intent-gate`
        
    2. `existing-page-check`
        
    3. `monthly-topic-research`
        
    4. `seo-structure-check`
        
    5. `maai-house-style-check`
        
    6. `claim-source-ledger`
        
    7. `media-check`
        
    8. `conversion-check`
        
    9. `interlinking-indexing-check`
        
    10. `ai-search-readiness-check`
        

    Each skill should include:

    - **When to use**
        
    - **Required inputs**
        
    - **Procedure**
        
    - **Pass/fail criteria**
        
    - **Common failure modes**
        
    - **Output template**
        
    - **Verification**
        

    That matches Hermes’ skill structure well. ([Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills "Skills System | Hermes Agent"))

    ---

    ## Tooling I’d wire through MCP first

    Prefer APIs/MCP over browser automation wherever possible.

    ### Must-have integrations

    |Integration|Why|
    |---|---|
    |**Google Search Console**|Query positions, impressions, pages, sitemaps, index inspection.|
    |**SEMrush**|Volume, KD, competitor/keyword opportunity metrics.|
    |**Content calendar**|Google Sheets, Airtable, Notion, or whatever Mahima’s calendar actually is.|
    |**CMS**|WordPress/Webflow/custom CMS draft creation and metadata updates.|
    |**Site crawler**|Existing URL inventory, internal links, heading structure, sitemap checks.|
    |**Source ledger store**|Database/table for claims, URLs, source dates, verification status.|
    |**Slack/email**|Human approvals and outreach drafts.|

    Hermes MCP is a good fit here because it can expose only the safe subset of tools from each server, instead of giving the agent broad uncontrolled access. ([Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp/ "MCP (Model Context Protocol) | Hermes Agent"))

    ---

    ## What should be deterministic vs LLM-reviewed

    A reliable build should not ask the model to “judge everything.” Use code for checks that are mechanical.

    ### Deterministic checks

    - No em dashes.
        
    - Banned filler phrase detection.
        
    - One H1 only.
        
    - H2/H3 hierarchy.
        
    - Keyword in H1.
        
    - Keyword in first paragraph.
        
    - TLDR near top.
        
    - Meta title present.
        
    - Meta description present.
        
    - Slug present.
        
    - Alt text present.
        
    - Image filename uses hyphens.
        
    - Internal link count.
        
    - Source ledger completeness.
        
    - CTA presence.
        
    - Sitemap URL present.
        
    - Draft vs published state.
        

    ### LLM-assisted checks

    - Intent match.
        
    - Buyer/user/warm-lead fit.
        
    - Whether an existing page can satisfy the keyword.
        
    - H2 usefulness.
        
    - EEAT fit.
        
    - Tone and naturalness.
        
    - Competitor neutrality.
        
    - Claim-source adequacy.
        
    - AI search readiness.
        
    - Whether the piece “feels built for this reader.”
        

    That hybrid approach is much more reliable than an all-LLM checklist.

    ---

    ## Where I would keep humans in the loop

    The following should remain human approval gates:

    1. **Monthly topic lock**
        
        - The agent can shortlist, but Kriti/Mahima should approve the calendar.
            
    2. **Existing vs new URL decision for strategic pages**
        
        - The agent can recommend, but URL strategy has compounding SEO consequences.
            
    3. **Final factual review**
        
        - The SOP explicitly requires a human to read the full post line by line and verify claims.
            
    4. **Competitor comparisons**
        
        - The agent can flag negative framing, but a human should approve comparison language.
            
    5. **Logo usage and recognizable companies**
        
        - Permission must be confirmed.
            
    6. **Publish action**
        
        - The agent can stage and prepare. Human approves live publish.
            
    7. **Outreach emails**
        
        - The agent can draft and queue. Human approves sends.
            

    ---

    ## Feasibility risks

    ### 1. Logged-in SaaS UIs are brittle

    Hermes browser automation is capable, but SEMrush, Canva, GSC, WordPress, stock platforms, and email tools may have CAPTCHAs, changing UI, rate limits, and permission issues. Browser automation should be a fallback, not the primary integration path. Hermes’ browser tooling is strong, but APIs/MCP are cleaner for repeatable operations. ([Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/features/browser/ "Browser Automation | Hermes Agent"))

    ### 2. Profiles isolate state, not filesystem permissions

    Hermes profiles are useful because each profile can have its own config, API keys, memory, skills, cron jobs, and state. But profiles are not a security sandbox. The docs explicitly distinguish profile state from sandboxing, so you still need scoped API keys, MCP tool filtering, least-privilege CMS roles, and possibly Docker/remote execution for safer operations. ([Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/profiles/ "Profiles: Running Multiple Agents | Hermes Agent"))

    ### 3. “Request indexing” is not a clean general API step

    For ordinary blogs, do not design around the Google Indexing API. It is officially scoped to JobPosting and BroadcastEvent/livestream pages. Use sitemap updates, URL inspection/status checks, and browser/manual Search Console request-indexing steps where appropriate. ([Google for Developers](https://developers.google.com/search/apis/indexing-api/v3/quickstart?utm_source=chatgpt.com "Indexing API Quickstart | Google Search Central - Google Developers"))

    ### 4. Claim verification cannot be fully delegated

    Hermes can make fact-checking dramatically easier by extracting claims, finding sources, and failing unsupported assertions. But the SOP’s Phase 4 should stay a human gate.

    ---

    ## Recommended MVP

    Build this first:

    ### 1. One Hermes profile: `kriti-content-ops`

    With:

    - SOP skills
        
    - GSC connector
        
    - SEMrush connector
        
    - content calendar connector
        
    - site crawler
        
    - draft checker
        
    - source ledger
        
    - Slack/email approval notifications
        

    ### 2. Two commands

    ```text
    /monthly-topic-research
    ```

    Produces the monthly topic shortlist.

    ```text
    /blog-gate <draft-url-or-doc>
    ```

    Produces a pass/fail gate report.

    ### 3. One cron job

    Run the monthly research skill on a schedule and deliver the shortlist to the team. Hermes cron supports recurring tasks, skills attached to cron jobs, and delivery to chat/files/platform targets. ([Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/features/cron "Scheduled Tasks (Cron) | Hermes Agent"))

    ### 4. One hard rule

    The agent may create drafts and reports, but it may not publish.

    ---

    ## Production version

    Once the MVP works, split into profiles:

    ```text
    kriti-orchestrator
    kriti-research
    kriti-brief
    kriti-gatekeeper
    kriti-media
    kriti-publisher
    ```

    Use Kanban for workflow state, not ad hoc chat threads.

    Use hooks to:

    - log every gate run,
        
    - record every source checked,
        
    - block publish actions unless a gate report is passing,
        
    - alert a human when an agent hits too many steps,
        
    - write audit records for CMS mutations. ([Hermes Agent](https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks "Event Hooks | Hermes Agent"))
        

    ---

    ## Bottom line

    **Neat fit for an agentic content operations system. Poor fit for unsupervised autopublishing.**

    I’d pitch it to Kriti as:

    > “We can turn your SOP into a Hermes-backed production line. Hermes will research, score, brief, QA, source-check, and prepare posts, but the system will deliberately fail closed and keep humans in control of topic approval, factual review, permissions, and publishing.”

    That framing matches the SOP, uses Hermes’ strengths, and avoids pretending the risky parts are solved just because an agent can click around a browser.