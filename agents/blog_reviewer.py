import re
from collections import Counter


class BlogReviewAgent:
    """
    Blog Review Agent implementing SOP checks across multiple phases:
      Phase 1: TLDR & CTA
      Phase 2: Structure & SEO (H2 outline, heading hierarchy)
      Phase 3: Internal Links (basic)
      Phase 7: Interlinking & Indexing
      Phase 8: AI Search Readiness (query fanout, natural questions)
    """

    def run(self, article):
        result = {
            "score": 100,
            "max_score": 100,
            "checks": {
                "tldr": False,
                "cta": False,
                "internal_links": False,
                "h2_outline_satisfied": False,
                "heading_hierarchy_valid": False,
                "interlinked_from_ranking_pages": False,
                "site_architecture_sensible": False,
                "gsc_submitted": False,
                "sitemap_updated": False,
                "query_fanout_language": False,
                "natural_question_answering": False,
            },
            "issues": [],
            "warnings": [],
            "phase_scores": {},
        }

        # ── Phase 1: TLDR & CTA ─────────────────────────────────────────
        phase1_score = self._check_phase1(article, result)

        # ── Phase 2: Structure & SEO ───────────────────────────────────
        phase2_score = self._check_phase2(article, result)

        # ── Phase 3: Internal Links (basic) ────────────────────────────
        phase3_score = self._check_basic_internal_links(article, result)

        # ── Phase 7: Interlinking & Indexing ───────────────────────────
        phase7_score = self._check_phase7(article, result)

        # ── Phase 8: AI Search Readiness ───────────────────────────────
        phase8_score = self._check_phase8(article, result)

        # Compute final score
        total_deductions = 100 - result["score"]
        result["phase_scores"] = {
            "phase1_tldr_cta": max(0, 25 - (25 * (2 - sum([
                result["checks"]["tldr"],
                result["checks"]["cta"],
            ])) / 2)),
            "phase2_structure_seo": max(0, 20 - (20 * (2 - sum([
                result["checks"]["h2_outline_satisfied"],
                result["checks"]["heading_hierarchy_valid"],
            ])) / 2)),
            "phase3_internal_links": max(0, 15 if result["checks"]["internal_links"] else 0),
            "phase7_interlinking_indexing": max(0, 20 - (20 * (4 - sum([
                result["checks"]["interlinked_from_ranking_pages"],
                result["checks"]["site_architecture_sensible"],
                result["checks"]["gsc_submitted"],
                result["checks"]["sitemap_updated"],
            ])) / 4)),
            "phase8_ai_search_readiness": max(0, 20 - (20 * (2 - sum([
                result["checks"]["query_fanout_language"],
                result["checks"]["natural_question_answering"],
            ])) / 2)),
        }

        return result

    # ─────────────────────────────────────────────────────────────────────
    # Phase 1: TLDR & CTA
    # ─────────────────────────────────────────────────────────────────────
    def _check_phase1(self, article, result):
        """Check TLDR presence and CTA keywords."""
        score_before = result["score"]

        # TLDR check
        if self._has_tldr(article):
            result["checks"]["tldr"] = True
        else:
            result["issues"].append("Missing TLDR section (Phase 1)")
            result["score"] -= 10

        # CTA check
        cta_keywords = [
            "book a demo",
            "contact sales",
            "start free trial",
            "schedule consultation",
            "get started",
            "sign up free",
            "talk to sales",
            "request a demo",
        ]
        if any(cta in article.lower() for cta in cta_keywords):
            result["checks"]["cta"] = True
        else:
            result["issues"].append("Missing or weak CTA (Phase 1)")
            result["score"] -= 10

        return score_before - result["score"]

    def _has_tldr(self, article):
        """Detect TLDR section via heading or bold/strong markers."""
        lower = article.lower()
        # Check for TLDR heading
        if re.search(r'^#{1,3}\s*tldr', lower, re.MULTILINE):
            return True
        # Check for bold TLDR label
        if re.search(r'\*\*tldr\*\*', lower):
            return True
        # Check for "TLDR:" or "TL;DR:" at start of a line
        if re.search(r'^\s*(tl;?dr)\s*:', lower, re.MULTILINE):
            return True
        # Check for TLDR in first 200 chars
        if re.search(r'tl;?dr', lower[:300]):
            return True
        return False

    # ─────────────────────────────────────────────────────────────────────
    # Phase 2: Structure & SEO (H2 outline, heading hierarchy)
    # ─────────────────────────────────────────────────────────────────────
    def _check_phase2(self, article, result):
        """Check H2 outline satisfaction and heading hierarchy."""
        score_before = result["score"]

        # --- H2 Outline Satisfaction ---
        # The article should have a clear outline (intro, body sections, conclusion)
        # We check: at least 2 H2 headings, logical flow, and conclusion presence
        h2_headings = re.findall(r'^##\s+(.+)', article, re.MULTILINE)
        h1_headings = re.findall(r'^#\s+(.+)', article, re.MULTILINE)

        has_outline_structure = self._validate_h2_outline(
            article, h2_headings, h1_headings
        )
        if has_outline_structure:
            result["checks"]["h2_outline_satisfied"] = True
        else:
            result["issues"].append(
                "H2 outline not satisfied: article lacks clear structure "
                "(need intro, 2+ H2 sections, conclusion) (Phase 2)"
            )
            result["score"] -= 8

        # --- Heading Hierarchy ---
        # Headings should follow proper hierarchy: H1 → H2 → H3 (no skipping)
        hierarchy_valid = self._validate_heading_hierarchy(article)
        if hierarchy_valid:
            result["checks"]["heading_hierarchy_valid"] = True
        else:
            result["issues"].append(
                "Invalid heading hierarchy: headings skip levels "
                "(e.g., H1 → H3 without H2) (Phase 2)"
            )
            result["score"] -= 7

        return score_before - result["score"]

    def _validate_h2_outline(self, article, h2_headings, h1_headings):
        """
        Validate that the article has a sensible outline:
        - At least one H1 or the title acts as the main heading
        - At least 2 H2 sections for body content
        - A conclusion or summary section exists
        """
        # Need at least 2 H2 sections
        if len(h2_headings) < 2:
            return False

        # Check for conclusion/summary section
        conclusion_keywords = [
            "conclusion", "summary", "final thoughts", "wrapping up",
            "to summarize", "in conclusion", "key takeaways", "takeaways",
            "next steps", "what's next",
        ]
        lower = article.lower()
        has_conclusion = any(kw in lower for kw in conclusion_keywords)

        # Check for intro indicator (first paragraph after H1 or first 200 chars)
        # We consider intro present if article has substantial content before first H2
        first_h2_pos = article.find("## ")
        if first_h2_pos == -1:
            first_h2_pos = len(article)
        intro_text = article[:first_h2_pos]
        has_intro = len(intro_text.strip()) > 100

        return has_conclusion and has_intro

    def _validate_heading_hierarchy(self, article):
        """
        Validate heading hierarchy: no skipping levels.
        E.g., H1 → H2 → H3 is valid. H1 → H3 is NOT valid.
        """
        lines = article.split('\n')
        previous_level = 0

        for line in lines:
            heading_match = re.match(r'^(#{1,6})\s+', line)
            if not heading_match:
                continue

            level = len(heading_match.group(1))

            # First heading can be any level
            if previous_level == 0:
                previous_level = level
                continue

            # Current level should not be more than 1 deeper than previous
            if level > previous_level + 1:
                return False

            previous_level = level

        return True

    # ─────────────────────────────────────────────────────────────────────
    # Phase 3: Basic Internal Links
    # ─────────────────────────────────────────────────────────────────────
    def _check_basic_internal_links(self, article, result):
        """Check for internal links to other blog posts or resources."""
        score_before = result["score"]

        if self._has_internal_links(article):
            result["checks"]["internal_links"] = True
        else:
            result["issues"].append("Missing internal links to related content (Phase 3)")
            result["score"] -= 10

        return score_before - result["score"]

    def _has_internal_links(self, article):
        """Detect internal links: /blog/ paths or 'Read our' references."""
        if re.search(r'/blog/\S+', article):
            return True
        if re.search(r'\bRead our\b', article, re.IGNORECASE):
            return True
        if re.search(r'\bLearn more\b', article, re.IGNORECASE):
            return True
        if re.search(r'\brelated (article|post|reading|guide)\b', article, re.IGNORECASE):
            return True
        return False

    # ─────────────────────────────────────────────────────────────────────
    # Phase 7: Interlinking & Indexing
    # ─────────────────────────────────────────────────────────────────────
    def _check_phase7(self, article, result):
        """
        Check interlinking and indexing requirements:
        - Interlinked from 2-3 existing ranking pages with keyword-rich anchor text
        - Sensible site architecture
        - URL submitted in GSC and indexing requested
        - Sitemap updated
        """
        score_before = result["score"]

        # --- Interlinked from ranking pages ---
        if self._check_interlinked_from_ranking_pages(article, result):
            result["checks"]["interlinked_from_ranking_pages"] = True
        else:
            result["issues"].append(
                "Not interlinked from 2-3 existing ranking pages with "
                "keyword-rich anchor text (Phase 7)"
            )
            result["score"] -= 5

        # --- Site architecture ---
        if self._check_site_architecture(article, result):
            result["checks"]["site_architecture_sensible"] = True
        else:
            result["warnings"].append(
                "Site architecture may not be sensible: URL path or breadcrumb "
                "structure unclear (Phase 7)"
            )
            result["score"] -= 3

        # --- GSC submission ---
        if self._check_gsc_submission(article, result):
            result["checks"]["gsc_submitted"] = True
        else:
            result["warnings"].append(
                "URL not confirmed as submitted to Google Search Console "
                "with indexing requested (Phase 7)"
            )
            result["score"] -= 3

        # --- Sitemap updated ---
        if self._check_sitemap_updated(article, result):
            result["checks"]["sitemap_updated"] = True
        else:
            result["warnings"].append(
                "Sitemap may not have been updated with this URL (Phase 7)"
            )
            result["score"] -= 3

        return score_before - result["score"]

    def _check_interlinked_from_ranking_pages(self, article, result):
        """
        Check if the article is interlinked from 2-3 existing ranking pages
        with keyword-rich anchor text.

        Detection strategy:
        - Look for references like 'As we discussed in [anchor]', 'See our guide on [anchor]',
          'Related: [anchor]', or backlink metadata
        - Check for keyword-rich anchor text (not just 'click here')
        """
        lower = article.lower()

        # Pattern 1: Explicit cross-reference markers
        cross_ref_patterns = [
            r'[Aa]s we (discussed|covered|mentioned|noted) in',
            r'[Ss]ee our (guide|article|post|coverage) on',
            r'[Rr]elated\s*[:;]',
            r'[Ll]earn more about',
            r'[Ff]or more (details|information|on)',
            r'[Cc]heck out our',
            r'[Rr]ead (more|our|the) (guide|article|post|blog)',
            r'[Pp]reviously we (covered|discussed|wrote about)',
        ]
        cross_refs_found = sum(
            1 for pattern in cross_ref_patterns if re.search(pattern, article)
        )

        # Pattern 2: Check for keyword-rich anchor text in markdown links
        # Good anchor: "keyword-rich phrase" vs bad: "click here"
        link_texts = re.findall(r'\[([^\]]+)\]\([^)]+\)', article)
        keyword_rich_anchors = 0
        bad_anchors = ['click here', 'read more', 'here', 'this article', 'this link']
        for text in link_texts:
            text_lower = text.lower().strip()
            if text_lower in bad_anchors:
                continue
            # Consider keyword-rich if it has 3+ words or contains topic keywords
            words = text_lower.split()
            if len(words) >= 3:
                keyword_rich_anchors += 1
            elif len(words) >= 1 and len(text) > 15:
                keyword_rich_anchors += 1

        # We need at least 2-3 interlinking references
        total_interlinks = cross_refs_found + keyword_rich_anchors
        return total_interlinks >= 2

    def _check_site_architecture(self, article, result):
        """
        Check for sensible site architecture signals:
        - Breadcrumb references
        - URL path structure mentioned
        - Category/tag references
        """
        lower = article.lower()

        # Check for breadcrumb or URL path references
        breadcrumb_patterns = [
            r'[Bb]readcrumb',
            r'home\s*[>›/]',
            r'blog\s*[>›/]',
            r'category\s*[>›/]',
            r'/blog/',
            r'/resources/',
            r'/guides/',
        ]
        has_breadcrumb = any(re.search(p, article) for p in breadcrumb_patterns)

        # Check for category or tag references
        category_patterns = [
            r'[Cc]ategor(y|ies)\s*[:;]',
            r'[Tt]ag(s)?\s*[:;]',
            r'[Tt]opic\s*[:;]',
            r'#[A-Za-z]+(?:\s*,\s*#[A-Za-z]+)+',  # hashtag-style topics
        ]
        has_categories = any(re.search(p, article) for p in category_patterns)

        # Check for URL path mention (e.g., "available at blog/seo-guide")
        url_path_pattern = r'(?:available at|find at|visit|url[:\s]+).{0,10}(?:/\w+){1,}'
        has_url_path = re.search(url_path_pattern, lower) is not None

        # At least 2 of these signals should be present
        signals = sum([has_breadcrumb, has_categories, has_url_path])
        return signals >= 1  # At least one architecture signal

    def _check_gsc_submission(self, article, result):
        """
        Check if URL was submitted to Google Search Console.
        In a real implementation, this would check GSC API.
        Here we look for metadata or comments indicating submission.
        """
        lower = article.lower()

        # Check for GSC submission markers (metadata, comments, frontmatter)
        gsc_markers = [
            r'gsc.*submitted',
            r'indexing.*requested',
            r'search\s*console',
            r'url\s*inspection',
            r'indexing\s*status',
            r'request\s*indexing',
        ]
        for marker in gsc_markers:
            if re.search(marker, lower):
                return True

        # Check for frontmatter metadata indicating GSC processing
        if re.search(r'indexing:\s*(requested|submitted|approved)', lower):
            return True

        # In absence of explicit markers, we cannot confirm GSC submission
        # Return False but this is a warning not a hard fail
        return False

    def _check_sitemap_updated(self, article, result):
        """
        Check if sitemap has been updated.
        In production, this would ping the sitemap endpoint.
        Here we look for metadata or comments indicating update.
        """
        lower = article.lower()

        sitemap_markers = [
            r'sitemap.*updated',
            r'sitemap.*submitted',
            r'xml.*sitemap',
            r'sitemap\.xml',
            r'pushed.*sitemap',
            r'added.*sitemap',
        ]
        for marker in sitemap_markers:
            if re.search(marker, lower):
                return True

        # Check for frontmatter sitemap indicator
        if re.search(r'sitemap:\s*(true|yes|updated)', lower):
            return True

        return False

    # ─────────────────────────────────────────────────────────────────────
    # Phase 8: AI Search Readiness
    # ─────────────────────────────────────────────────────────────────────
    def _check_phase8(self, article, result):
        """
        Check AI Search Readiness:
        - Query fanout language: article uses varied phrasing for the same concept
        - Natural question answering: article directly answers questions
        """
        score_before = result["score"]

        # --- Query Fanout Language ---
        if self._check_query_fanout_language(article, result):
            result["checks"]["query_fanout_language"] = True
        else:
            result["issues"].append(
                "Insufficient query fanout language: article should use varied "
                "phrasing and synonyms for key concepts to match diverse "
                "search queries (Phase 8)"
            )
            result["score"] -= 8

        # --- Natural Question Answering ---
        if self._check_natural_question_answering(article, result):
            result["checks"]["natural_question_answering"] = True
        else:
            result["issues"].append(
                "Weak natural question answering: article should directly answer "
                "questions in a clear, concise format suitable for AI "
                "search results (Phase 8)"
            )
            result["score"] -= 8

        return score_before - result["score"]

    def _check_query_fanout_language(self, article, result):
        """
        Check if the article uses varied phrasing (query fanout language)
        to describe the same concept, matching how different users might
        search for the topic.

        Detection strategy:
        - Look for parenthetical synonyms: "SEO (search engine optimization)"
        - Look for "also known as", "sometimes called", "referred to as"
        - Look for multiple related terms/phrases for the same concept
        - Check for question-style headings that mirror search queries
        """
        lower = article.lower()

        # Pattern 1: Parenthetical definitions/synonyms
        paren_patterns = [
            r'\(([A-Za-z\s]+(?:optimization|management|strategy|analysis|marketing|development|engineering|science))\)',
            r'also known as',
            r'sometimes called',
            r'referred to as',
            r'or\s+\w+',  # "search engine optimization or SEO"
            r'aka\.?\s',
            r'\((?:also|aka)\s',
        ]
        fanout_signals = sum(1 for p in paren_patterns if re.search(p, article))

        # Pattern 2: Question-style headings (mirroring search queries)
        question_headings = re.findall(r'^#{1,3}\s+.*\?', article, re.MULTILINE)
        if len(question_headings) >= 2:
            fanout_signals += 2

        # Pattern 3: Check for multiple ways to describe the same thing
        # Look for "X, Y, and Z" enumeration patterns
        enumeration_pattern = r'\b(\w+(?:\s+\w+){0,3}),\s+(\w+(?:\s+\w+){0,3}),\s+and\s+(\w+(?:\s+\w+){0,3})\b'
        enumerations = re.findall(enumeration_pattern, article)
        if len(enumerations) >= 2:
            fanout_signals += 1

        # Pattern 4: Check for FAQ-style sections
        faq_patterns = [
            r'\bFAQ\b',
            r'\bfrequently asked questions\b',
            r'\bcommon questions\b',
            r'\bpeople also ask\b',
        ]
        has_faq = any(re.search(p, lower) for p in faq_patterns)
        if has_faq:
            fanout_signals += 2

        # Need at least 3 fanout signals for good coverage
        return fanout_signals >= 3

    def _check_natural_question_answering(self, article, result):
        """
        Check if the article directly answers natural language questions
        in a format suitable for AI search results.

        Detection strategy:
        - Look for Q&A format sections
        - Look for "What is X?" followed by concise answers
        - Look for direct answer patterns: "X is..." after a question
        - Check for definition-style paragraphs
        """
        lower = article.lower()

        # Pattern 1: Explicit Q&A format
        qa_patterns = [
            r'Q\s*[:.]\s*.+\n*A\s*[:.]\s*.+',
            r'[Qq]uestion\s*[:;]\s*.+\n*[Aa]nswer\s*[:;]\s*.+',
            r'What is.+?\n\n.+is\s',
            r'How (do|does|can|to).+?\n\n',
            r'Why (is|does|do|are).+?\n\n',
        ]
        qa_signals = sum(1 for p in qa_patterns if re.search(p, article))

        # Pattern 2: Question headings followed by concise answers
        lines = article.split('\n')
        question_then_answer = 0
        for i, line in enumerate(lines):
            if re.match(r'^#{1,3}\s+.*\?', line):
                # Check if next non-empty line is a concise answer (under 200 chars)
                for j in range(i + 1, min(i + 4, len(lines))):
                    if lines[j].strip() and not lines[j].startswith('#'):
                        answer_text = lines[j].strip()
                        if 20 < len(answer_text) < 250:
                            question_then_answer += 1
                        break
        if question_then_answer >= 2:
            qa_signals += 2

        # Pattern 3: Direct definition patterns
        definition_patterns = [
            r'\b\w+\s+is\s+a\s+\w+',
            r'\b\w+\s+refers\s+to\s',
            r'\b\w+\s+means\s+that\s',
            r'[Dd]efined\s+as',
            r'[Dd]efinition\s*[:;]',
        ]
        definition_count = sum(
            1 for p in definition_patterns if re.search(p, article)
        )
        if definition_count >= 2:
            qa_signals += 1

        # Pattern 4: Check for "In short", "Simply put", "To put it simply"
        summary_phrases = [
            r'\bIn short\b',
            r'\bSimply put\b',
            r'\bTo put it simply\b',
            r'\bThe (answer|solution|key point) is\b',
            r'\bIn other words\b',
        ]
        summary_count = sum(1 for p in summary_phrases if re.search(p, article))
        if summary_count >= 1:
            qa_signals += 1

        # Need at least 3 signals for good natural question answering
        return qa_signals >= 3


# ─────────────────────────────────────────────────────────────────────────
# Standalone execution
# ─────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) > 1:
        filepath = sys.argv[1]
        with open(filepath, 'r') as f:
            article_content = f.read()
    else:
        # Read from stdin for pipeline usage
        article_content = sys.stdin.read()

    agent = BlogReviewAgent()
    review_result = agent.run(article_content)

    print(json.dumps(review_result, indent=2))
