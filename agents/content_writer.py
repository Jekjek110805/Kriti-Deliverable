class ContentWriterAgent:
    def run(self, brief):
        title = brief.get("recommended_h1")
        keyword = brief.get("keyword")

        article = f"""
# {title}

## TLDR

{keyword} can help organizations improve efficiency, streamline operations, and support growth.

## What is {keyword}?

This section introduces the topic.

## Why {keyword} matters

This section explains business value.

## How to choose {keyword}

This section helps readers evaluate options.

## Frequently Asked Questions

"""

        for question in brief.get("faq_questions", []):
            article += f"\n### {question}\nAnswer pending.\n"

        article += """

## Conclusion

Summarize the key points.

## Call To Action

Book a demo or contact the team to learn more.
"""

        return {
            "title": title,
            "keyword": keyword,
            "draft": article,
            "status": "Draft Generated"
        }
