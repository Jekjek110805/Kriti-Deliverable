"""
LiteLLM Client for Kriti Agents

Used ONLY for language-generation enrichment features (not Stage 1A scoring):
  - Executive narrative summary
  - AI-generated audience questions & H2 headings
  - SEO score explanations

Stage 1A opportunity scoring is PURE PYTHON (hermes_client.py).
This client is NOT used for deterministic scoring decisions.
"""
import os
import json
import urllib.request
import urllib.error
from dotenv import load_dotenv

load_dotenv()


class LiteLLMClient:
    def __init__(self):
        from dotenv import load_dotenv
        import os as _os
        _env_path = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), '.env')
        load_dotenv(_env_path)
        self.base_url = os.getenv("LITELLM_BASE_URL", "")
        self.api_key = self._load_key()
        self.model = os.getenv("LITELLM_MODEL", "fast-model")

    def _load_key(self):
        key = os.getenv("LITELLM_API_KEY", "")
        if key:
            return key
        key_file = os.getenv("LITELLM_KEY_FILE", "")
        if key_file and os.path.exists(key_file):
            with open(key_file) as f:
                return f.read().strip()
        return ""

    def _headers(self):
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def chat(self, messages, temperature=0.3, max_tokens=500):
        if not self.base_url:
            return "[LiteLLM not configured: set LITELLM_BASE_URL env var]"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        body = json.dumps(payload).encode()
        url = f"{self.base_url}/v1/chat/completions"
        req = urllib.request.Request(url, data=body, headers=self._headers(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
            return data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            return f"[LiteLLM error {e.code}: {e.read().decode()[:200]}]"
        except Exception as e:
            return f"[LiteLLM connection error: {e}]"

    def generate_audience_questions(self, keyword, intent, count=5):
        prompt = (
            f"You are an SEO content strategist. For the keyword '{keyword}' "
            f"with intent '{intent}', generate {count} realistic questions "
            f"that target audience would ask. Return ONLY a JSON list of strings."
        )
        result = self.chat([{"role": "user", "content": prompt}], temperature=0.7)
        try:
            return json.loads(result)
        except (json.JSONDecodeError, TypeError):
            return [q.strip() for q in result.split("\n") if q.strip() and "?" in q][:count]

    def generate_h2s(self, keyword, topic, intent, count=4):
        prompt = (
            f"You are a content editor. For an article about '{topic}' "
            f"(keyword: '{keyword}', intent: {intent}), suggest {count} "
            f"compelling H2 headings. Return ONLY a JSON list of strings."
        )
        result = self.chat([{"role": "user", "content": prompt}], temperature=0.6)
        try:
            return json.loads(result)
        except (json.JSONDecodeError, TypeError):
            return [h.strip() for h in result.split("\n") if h.strip()][:count]

    def generate_explanation(self, keyword, scores_dict):
        prompt = (
            f"You are an SEO analyst explaining results to a marketing manager. "
            f"For the keyword '{keyword}', the opportunity scores are: {json.dumps(scores_dict, indent=2)}. "
            f"Explain in 2-3 sentences why this topic received these scores and what action makes sense."
        )
        return self.chat([{"role": "user", "content": prompt}], temperature=0.4)

    def generate_executive_narrative(self, summary_dict):
        prompt = (
            f"You are a content strategist writing an executive summary for a marketing director. "
            f"Based on this data: {json.dumps(summary_dict, indent=2)}, "
            f"write a concise (3-4 sentence) narrative summary of the content opportunity landscape."
        )
        return self.chat([{"role": "user", "content": prompt}], temperature=0.4)

    def generate_content_section(self, keyword: str, intent: str, h2_title: str,
                                tone: str, word_target: int = 200) -> str:
        """Generate a unique content section for a specific H2 heading.

        The content is NOT templated — each section is generated independently
        by the LLM with full context about the keyword and heading.
        """
        intent_guidance = {
            "BOFU": "Focus on helping the reader make a decision. Compare options, highlight benefits, and guide toward action.",
            "MOFU": "Focus on research and evaluation. Explain how things work, what to look for, and why it matters.",
            "TOFU": "Focus on education and awareness. Define concepts, explain context, and help the reader understand the topic.",
        }
        guidance = intent_guidance.get(intent, "Inform and engage the reader.")

        prompt = (
            f"You are an expert SEO content writer. Write a section for an article "
            f"about '{keyword}' with the H2 heading '{h2_title}'.\n\n"
            f"Intent: {intent}. {guidance}\n"
            f"Tone: {tone}.\n"
            f"Target length: approximately {word_target} words.\n\n"
            f"RULES:\n"
            f"- Write ORIGINAL content — never use placeholder text like '[Content for: ...]'.\n"
            f"- Do NOT start with a generic intro like 'In this section...'.\n"
            f"- Include specific, actionable advice where possible.\n"
            f"- Use concrete examples, numbers, or scenarios.\n"
            f"- Write in second person (you/your).\n"
            f"- Keep paragraphs short (max 150 words each).\n"
            f"- Output ONLY the section content — no heading, no meta-commentary.\n"
            f"- Do NOT use markdown # headings in your output — just the paragraph text.\n"
        )
        return self.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=min(word_target * 3, 2000),
        )

    def generate_faq_answer(self, keyword: str, question: str, tone: str) -> str:
        """Generate a unique FAQ answer — never templated."""
        prompt = (
            f"You are an expert in '{keyword}'. Answer the following question concisely.\n\n"
            f"Question: {question}\n\n"
            f"Tone: {tone}\n"
            f"RULES:\n"
            f"- Answer directly and specifically.\n"
            f"- Never say 'Answer pending' or 'Learn about...'.\n"
            f"- Use 2-4 sentences max.\n"
            f"- Include a concrete detail or example where possible.\n"
            f"- Output ONLY the answer text.\n"
        )
        return self.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=300,
        )

    def generate_tldr(self, keyword: str, intent: str, tone: str) -> str:
        """Generate a unique TLDR paragraph — never templated, no # headers."""
        prompt = (
            f"Write a TL;DR (2-3 sentences) for an article about '{keyword}' "
            f"with {intent} intent.\n\n"
            f"Tone: {tone}\n"
            f"RULES:\n"
            f"- Summarize the key takeaway and action.\n"
            f"- Never use 'This guide covers everything you need to know...'.\n"
            f"- Be specific and actionable.\n"
            f"- Output ONLY the TLDR text — no # headers, no markdown formatting.\n"
        )
        return self.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=200,
        )

    def generate_cta(self, keyword: str, intent: str, tone: str) -> str:
        """Generate a unique CTA — never templated, no # headers."""
        prompt = (
            f"Write a call-to-action (1-2 sentences) for an article about '{keyword}' "
            f"with {intent} intent.\n\n"
            f"Tone: {tone}\n"
            f"RULES:\n"
            f"- Never use 'Ready to get started with...'.\n"
            f"- Make it specific to the keyword and intent.\n"
            f"- Include a clear next step.\n"
            f"- Output ONLY the CTA text — no # headers, no markdown formatting.\n"
        )
        return self.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=150,
        )


client = LiteLLMClient()
