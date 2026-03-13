from __future__ import annotations

from typing import Any


KNOWLEDGE_BASE = [
    {
        "id": "shipping-policy",
        "title": "Shipping Times and Tracking",
        "content": (
            "Orders usually ship within 1 to 2 business days. "
            "Customers receive a tracking number once the package leaves the warehouse. "
            "Standard shipping takes 3 to 5 business days."
        ),
    },
    {
        "id": "returns-policy",
        "title": "Returns and Refunds",
        "content": (
            "Returns are accepted within 30 days of delivery. "
            "Refunds are processed after the returned item is inspected. "
            "Damaged items can be escalated to support for expedited handling."
        ),
    },
    {
        "id": "account-help",
        "title": "Account and Profile Help",
        "content": (
            "Customers can update their address, password, and communication preferences "
            "from the account settings page."
        ),
    },
]


class KnowledgeBaseTool:
    """Simple in-memory connector for support documentation."""

    def search_knowledge_base(self, query: str) -> dict[str, Any]:
        normalized = query.lower().strip()
        scored_articles = []
        for article in KNOWLEDGE_BASE:
            haystack = f"{article['title']} {article['content']}".lower()
            score = sum(1 for token in normalized.split() if token in haystack)
            if score > 0:
                scored_articles.append(
                    {
                        "id": article["id"],
                        "title": article["title"],
                        "content": article["content"],
                        "score": score,
                    }
                )

        scored_articles.sort(key=lambda item: item["score"], reverse=True)
        return {
            "query": query,
            "results": scored_articles[:3],
        }
