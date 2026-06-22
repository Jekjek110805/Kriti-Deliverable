class BlogReviewAgent:
    def run(self, article):
        result = {
            "score": 100,
            "checks": {
                "tldr": False,
                "cta": False,
                "internal_links": False
            },
            "issues": []
        }

        # TLDR check
        if "tldr" in article.lower():
            result["checks"]["tldr"] = True
        else:
            result["issues"].append("Missing TLDR")
            result["score"] -= 10

        # CTA check
        cta_keywords = [
            "book a demo",
            "contact sales",
            "start free trial",
            "schedule consultation"
        ]

        if any(cta in article.lower() for cta in cta_keywords):
            result["checks"]["cta"] = True
        else:
            result["issues"].append("Missing CTA")
            result["score"] -= 10

        # Internal link check
        if "/blog/" in article or "Read our" in article:
            result["checks"]["internal_links"] = True
        else:
            result["issues"].append("Missing Internal Links")
            result["score"] -= 10

        return result
