"""Web search tool using Exa AI"""

import os
import json
import requests
from crewai.tools import tool

from app.config import logger


@tool("web_search")
def web_search_tool(
    query: str,
    include_domains: list[str] | None = None,
    category: str | None = None,
    search_type: str = "auto",
) -> str:
    """Search the web for information using Exa AI.

    Args:
        query: The search query
        include_domains: Optional list of domains to search within (e.g., ["linkedin.com", "company.com"])
        category: Optional content category filter. Options: "linkedin profile", "company", "news", 
                 "financial report", "pdf". Omit to get all categories.
        search_type: Search algorithm to use. Options: "auto" (default), "neural", "deep"

    Returns:
        JSON string with search results including titles, URLs, summaries, and highlights
    """
    try:
        api_key = os.getenv("EXAAI_API_KEY")
        if not api_key:
            return json.dumps({"error": "EXAAI_API_KEY not configured"})

        headers = {"x-api-key": api_key, "Content-Type": "application/json"}

        payload = {
            "query": query,
            "type": search_type,
            "numResults": 20,
            "contents": {
                "highlights": True,
                "summary": True,
            },
            "subpages": 5,
            "extras": {"links": 5},
        }

        # Add optional parameters if provided
        if include_domains:
            payload["includeDomains"] = include_domains

        if category:
            payload["category"] = category

        response = requests.post(
            "https://api.exa.ai/search", headers=headers, json=payload, timeout=60
        )

        if response.status_code == 200:
            data = response.json()
            # Format results for the agent with all available fields
            formatted_results = []
            for result in data.get("results", []):
                formatted_result = {
                    "title": result.get("title", ""),
                    "url": result.get("url", ""),
                    "author": result.get("author"),
                    "publishedDate": result.get("publishedDate"),
                }

                # Add summary if available
                if result.get("summary"):
                    formatted_result["summary"] = result["summary"]

                # Add highlights if available (most relevant excerpts)
                if result.get("highlights"):
                    formatted_result["highlights"] = result["highlights"]

                formatted_results.append(formatted_result)

            return json.dumps(
                {
                    "searchType": data.get("resolvedSearchType", "unknown"),
                    "totalResults": len(formatted_results),
                    "results": formatted_results,
                },
                indent=2,
            )
        else:
            return json.dumps(
                {
                    "error": f"Exa API error: {response.status_code}",
                    "message": response.text,
                }
            )

    except Exception as e:
        logger.error(f"Web search error: {str(e)}")
        return json.dumps({"error": str(e)})


@tool("get_webpage_content")
def get_webpage_content(
    urls: list[str],
) -> str:
    """Fetch and extract content from specific webpages using Exa AI.

    This tool is useful when you have specific URLs and want to extract their full content,
    including text, summaries, and links. Use this after web_search to deep-dive into
    specific pages.

    Args:
        urls: List of URLs to fetch content from (e.g., ["https://example.com", "https://company.com/about"])
    Returns:
        JSON string with page contents including text, summaries, links, and metadata
    """
    try:
        api_key = os.getenv("EXAAI_API_KEY")
        if not api_key:
            return json.dumps({"error": "EXAAI_API_KEY not configured"})

        headers = {"x-api-key": api_key, "Content-Type": "application/json"}

        payload = {
            "ids": urls,
            "livecrawl": "preferred"
        }

        payload["summary"] = True

        payload["subpages"] = 4

        payload["extras"] = {"links": 5}

        response = requests.post(
            "https://api.exa.ai/contents", headers=headers, json=payload, timeout=90
        )

        if response.status_code == 200:
            data = response.json()
            formatted_results = []

            for result in data.get("results", []):
                formatted_result = {
                    "url": result.get("url", ""),
                    "title": result.get("title", ""),
                    "author": result.get("author"),
                    "publishedDate": result.get("publishedDate"),
                }

                # Add text content
                if result.get("text"):
                    formatted_result["text"] = result["text"]

                # Add summary if available
                if result.get("summary"):
                    formatted_result["summary"] = result["summary"]

                # Add extracted links
                if result.get("links"):
                    formatted_result["links"] = result["links"]

                formatted_results.append(formatted_result)

            return json.dumps(
                {"totalPages": len(formatted_results), "pages": formatted_results},
                indent=2,
            )
        else:
            return json.dumps(
                {
                    "error": f"Exa API error: {response.status_code}",
                    "message": response.text,
                }
            )

    except Exception as e:
        logger.error(f"Webpage content fetch error: {str(e)}")
        return json.dumps({"error": str(e)})
