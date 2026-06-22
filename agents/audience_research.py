import re
import json
import urllib.request
import urllib.parse


# ---------------------------------------------------------------------------
# PAA question classifier – keyword / pattern based
# ---------------------------------------------------------------------------

_QUESTION_PATTERNS = {
    "Buying Question": [
        r"\bbest\b", r"\bbuy\b", r"\bpurchase\b", r"\bprice\b", r"\bcost\b",
        r"\bworth (it|the|my|your|the money)\b",
        r"\bafford\b", r"\bcheap\b", r"\bexpensive\b",
        r"\bwhere (can|to|should) .*(buy|find|get|purchase)",
        r"\bwhich .*(should|would|could) (i|you) (buy|choose|pick|select|get)",
        r"\bshould i (buy|choose|pick|select|get|invest)",
        r"\bis .*(worth|good value|affordable)",
    ],
    "Comparison Question": [
        r"\bvs\.?\b", r"\bversus\b", r"\bcompare\b", r"\bcomparison\b",
        r"\bdifference between\b", r"\bdifferences between\b",
        r"\bwhich (is|are) (better|best|worse|good|bad)\b",
        r"\bhow does .*(compare|stack up|differ|differ from)",
        r"\b .*\b(or)\b .*\?",  # "X or Y?" pattern
    ],
    "Alternative Question": [
        r"\balternatives?\b", r"\breplacements?\b", r"\bsubstitutes?\b",
        r"\binstead of\b", r"\bother (options?|choices?|ways?)\b",
        r"\bwhat (else|other) (can|could|should|would)",
        r"\bare there (any )?(other|better) (options?|choices?|ways?|solutions?|tools?|products?|services?)\b",
    ],
    "Pain Point": [
        r"\bproblem\b", r"\bissue\b", r"\bstruggle\b", r"\bchallenge\b",
        r"\bfrustrat\b", r"\bannoy\b", r"\bdifficult\b", r"\bhard to\b",
        r"\bhow (to|do|can) (i|you|we) (fix|solve|resolve|overcome|deal with|handle|address|avoid|prevent|stop|reduce|manage)",
        r"\bwhy (is|does|do|are|can|will|won|doesn|don|isn) .*(so )?(hard|difficult|slow|broken|fail|error|bug|crash|pain|hassle|annoying|frustrat)",
        r"\bhow (to|do|can) (i|you|we) (stop|prevent|avoid|reduce|eliminate)",
    ],
    "Objection Question": [
        r"\bscam\b", r"\brip.?off\b", r"\bfake\b",
        r"\btrust\b", r"\btrustworthy\b", r"\breliable\b", r"\blegit\b",
        r"\bis .*(safe|secure|legit|reliable|trustworthy|worth (it|the|my|your|the money))\b",
        r"\bany (good|real) (review|testimonial|proof|evidence)",
        r"\bwhy (should|would|could) (i|anyone|we) (trust|use|pick|choose|buy|pay)",
    ],
    "Beginner Education": [
        r"\bwhat is\b", r"\bwhat are\b",
        r"\bhow (do|does|can|should|to) (i|you|we|it)\b",
        r"\bbeginner\b", r"\bnewbie\b", r"\bgetting started\b",
        r"\bguide\b", r"\btutorial\b", r"\blearn\b", r"\bexplain\b",
        r"\bhow (it|this|that) works?\b",
        r"\bwhat (does|do) .*(mean|refer to|stand for|do)\b",
    ],
}

# Compile once at module load
_COMPILED = {
    category: [re.compile(p, re.IGNORECASE) for p in patterns]
    for category, patterns in _QUESTION_PATTERNS.items()
}


def classify_question(question: str) -> str:
    """Classify a question string into one of 7 audience-research categories.

    Returns one of:
        Pain Point, Buying Question, Comparison Question, Alternative Question,
        Objection Question, Beginner Education, General Discussion
    """
    text = question.strip()

    # Score each category by counting matching patterns
    scores: dict[str, int] = {}
    for category, patterns in _COMPILED.items():
        hit = 0
        for pat in patterns:
            if pat.search(text):
                hit += 1
        if hit:
            scores[category] = hit

    if not scores:
        return "General Discussion"

    # Tie-break order: more specific categories first
    priority = [
        "Buying Question",
        "Comparison Question",
        "Alternative Question",
        "Pain Point",
        "Objection Question",
        "Beginner Education",
    ]
    best_score = max(scores.values())
    for cat in priority:
        if scores.get(cat) == best_score:
            return cat

    # Fallback to whichever scored highest
    return max(scores, key=scores.get)  # type: ignore[arg-type]


_SIGNAL_SCORES = {
    "Buying Question": 5,
    "Comparison Question": 5,
    "Alternative Question": 5,
    "Pain Point": 4,
    "Objection Question": 4,
    "Beginner Education": 2,
    "General Discussion": 0,
}


def score_signal(category: str) -> int:
    """Return a 0-5 commercial-intent signal score for a question category."""
    return _SIGNAL_SCORES.get(category, 0)


# ---------------------------------------------------------------------------
# Google PAA scraper – uses urllib + regex (no third-party deps)
# ---------------------------------------------------------------------------

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Google PAA questions appear inside JSON-LD blocks or data attributes.
# We try several extraction strategies.
_PAA_JSON_RE = re.compile(
    r'"PeopleAlsoAskQuestionsStore"\s*:\s*(\[.*?\])', re.DOTALL
)
_PAA_TITLE_RE = re.compile(
    r'"title"\s*:\s*"((?:[^"\\]|\\.)*)"', re.DOTALL
)
_PAA_DATA_RE = re.compile(
    r'data-q="((?:[^"\\]|\\.)*)"', re.DOTALL
)
_PAA_ALT_RE = re.compile(
    r'class="[^"]*related-question-pair[^"]*"[^>]*>(.*?)</(?:div|g-inner-card)',
    re.DOTALL | re.IGNORECASE,
)
_PAA_CLEAN_HTML_RE = re.compile(r'<[^>]+>')


def fetch_paa_questions(keyword: str, max_questions: int = 10) -> list[dict]:
    """Scrape Google 'People Also Ask' questions for *keyword*.

    Returns a list of dicts with keys:
        question (str), category (str), signal_score (int), source (str)

    On any failure returns an empty list so callers can fall back gracefully.
    """
    query = urllib.parse.quote_plus(keyword)
    url = f"https://www.google.com/search?q={query}&hl=en"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return []

    raw_questions: list[str] = []

    # Strategy 1 – JSON-LD / JS data blob
    m = _PAA_JSON_RE.search(html)
    if m:
        try:
            blob = json.loads(m.group(1))
            if isinstance(blob, list):
                for item in blob:
                    if isinstance(item, dict):
                        t = item.get("title") or item.get("question") or ""
                        if t:
                            raw_questions.append(t)
                    elif isinstance(item, str):
                        raw_questions.append(item)
        except (json.JSONDecodeError, TypeError):
            pass

    # Strategy 2 – data-q attributes (common in Google mobile/desktop markup)
    if not raw_questions:
        for m2 in _PAA_DATA_RE.finditer(html):
            q = _strip_html_entities(m2.group(1))
            if q and "?" in q:
                raw_questions.append(q)

    # Strategy 3 – generic title extraction from PAA-like JSON blobs
    if not raw_questions:
        for m3 in _PAA_TITLE_RE.finditer(html):
            q = _strip_html_entities(m3.group(1))
            if q and "?" in q and len(q) > 10:
                raw_questions.append(q)

    # Strategy 4 – related-question-pair CSS class
    if not raw_questions:
        for m4 in _PAA_ALT_RE.finditer(html):
            text = _PAA_CLEAN_HTML_RE.sub(" ", m4.group(1)).strip()
            text = _strip_html_entities(text)
            if text and "?" in text:
                raw_questions.append(text)

    # Deduplicate preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for q in raw_questions:
        q = q.strip()
        if q and q not in seen and len(q) > 5:
            seen.add(q)
            unique.append(q)
        if len(unique) >= max_questions:
            break

    results: list[dict] = []
    for q in unique:
        cat = classify_question(q)
        results.append({
            "question": q,
            "category": cat,
            "signal_score": score_signal(cat),
            "source": "google_paa",
        })

    return results


def _strip_html_entities(text: str) -> str:
    """Remove common HTML entities from *text*."""
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&quot;', '"', text)
    text = re.sub(r'&#39;', "'", text)
    text = re.sub(r'&apos;', "'", text)
    text = re.sub(r'&#x27;', "'", text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


# ---------------------------------------------------------------------------
# H2 / FAQ transformation helpers
# ---------------------------------------------------------------------------

def _to_h2(question: str) -> str:
    """Convert a question into a statement-style H2 heading."""
    q = question.strip()
    # Strip trailing question mark
    if q.endswith("?"):
        q = q[:-1].strip()
    # Replace leading interrogative patterns
    q = re.sub(r"^(what is|what are|how do|how does|how can|how should|how to|"
               r"why is|why does|why do|why are|why should|why would|why can|"
               r"which|where|when|who|is |are |do |does |can |should |would )",
               "", q, flags=re.IGNORECASE).strip()
    if q:
        q = q[0].upper() + q[1:]
    return q


def _to_faq(question: str) -> dict:
    """Return a simple FAQ dict from a question string."""
    return {
        "question": question.strip(),
        "answer_stub": f"Learn about {_to_h2(question).lower()}.",
    }


# ---------------------------------------------------------------------------
# Audience Research Agent
# ---------------------------------------------------------------------------

class AudienceResearchAgent:
    def run(self, topics):
        from integrations.litellm_client import client

        enriched_topics = []

        for topic in topics:
            keyword = topic["keyword"]
            intent = topic.get("intent", "Unknown")

            # --- 1. Deterministic fallback questions (always present) ---
            topic["audience_questions"] = [
                f"What is the best {keyword}?",
                f"How do I choose {keyword}?",
                f"Is {keyword} worth it for small clinics?"
            ]

            topic["suggested_h2s"] = [
                f"What is {keyword}?",
                f"How to choose {keyword}",
                f"Best use cases for {keyword}"
            ]

            # --- 2. Real PAA data (graceful fallback on failure) ---
            paa_questions: list[dict] = []
            try:
                paa_questions = fetch_paa_questions(keyword)
            except Exception:
                paa_questions = []

            if paa_questions:
                topic["paa_questions"] = paa_questions
                topic["paa_question_list"] = [q["question"] for q in paa_questions]
                topic["paa_categories"] = list({q["category"] for q in paa_questions})
                topic["paa_avg_signal"] = (
                    round(
                        sum(q["signal_score"] for q in paa_questions) / len(paa_questions),
                        2,
                    )
                    if paa_questions
                    else 0
                )
                # Merge PAA questions into audience_questions (deduped)
                existing = set(topic["audience_questions"])
                for q in paa_questions:
                    if q["question"] not in existing:
                        topic["audience_questions"].append(q["question"])
                        existing.add(q["question"])
                # H2 / FAQ transformations from PAA
                topic["paa_h2s"] = [_to_h2(q["question"]) for q in paa_questions]
                topic["paa_faqs"] = [_to_faq(q["question"]) for q in paa_questions]
            else:
                topic["paa_questions"] = []
                topic["paa_question_list"] = []
                topic["paa_categories"] = []
                topic["paa_avg_signal"] = 0
                topic["paa_h2s"] = []
                topic["paa_faqs"] = []

            # --- 3. AI enrichment (existing behaviour) ---
            try:
                enrichment = client.generate_audience_questions(keyword, intent)
                if enrichment and not str(enrichment[0]).startswith("[LiteLLM"):
                    topic["ai_audience_questions"] = enrichment
            except Exception:
                pass

            try:
                h2s = client.generate_h2s(keyword, topic.get("topic", keyword), intent)
                if h2s and not str(h2s[0]).startswith("[LiteLLM"):
                    topic["ai_h2s"] = h2s
            except Exception:
                pass

            enriched_topics.append(topic)

        return enriched_topics
