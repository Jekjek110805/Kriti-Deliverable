"""
LiteLLM Client for Kriti Agents
"""
import os
import json
import urllib.request
import urllib.error


class LiteLLMClient:
    def __init__(self):
        self.base_url = os.getenv("LITELLM_BASE_URL", "http://litellm-openrouter:4000")
        self.api_key = self._load_key()
        self.model = os.getenv("LITELLM_MODEL", "fast-model")

    def _load_key(self):
        key = os.getenv("LITELLM_API_KEY", "")
        if key:
            return key
        key_file = os.getenv("LITELLM_KEY_FILE", "/tmp/kriti-backend/config/litellm_key.txt")
        if os.path.exists(key_file):
            with open(key_file) as f:
                return f.read().strip()
        return ""

    def _headers(self):
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def chat(self, messages, temperature=0.3, max_tokens=500):
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


client = LiteLLMClient()
