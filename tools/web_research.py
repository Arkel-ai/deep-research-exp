"""Web research tool using Exa AI Research API"""

import os
import json
import time
import requests
from crewai.tools import tool

try:
    from app.config import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


@tool("web_research", max_usage_count=5)
def web_research_tool(instructions: str) -> str:
    """Conduct deep research on a topic.
    
    Args:
        instructions: The research instructions/query
        
    Returns:
        JSON string with research results or status
    """
    max_wait_seconds = 300
    try:
        api_key = os.getenv("EXAAI_API_KEY")
        if not api_key:
            logger.error("EXAAI_API_KEY not configured")
            return "research failed"
        
        headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json"
        }
        
        # Step 1: Initiate research
        payload = {
            "instructions": instructions,
            "model": "exa-research"
        }
        
        logger.info(f"Initiating research: {instructions}")
        
        response = requests.post(
            "https://api.exa.ai/research/v1",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code != 201:
            logger.error(f"Failed to initiate research: {response.status_code}")
            return "research failed"
        
        init_data = response.json()
        research_id = init_data.get("researchId")
        
        if not research_id:
            logger.error("No research ID returned")
            return "research failed"
        
        logger.info(f"Research initiated with ID: {research_id}")
        
        # Step 2: Poll for results
        poll_url = f"https://api.exa.ai/research/v1/{research_id}"
        start_time = time.time()
        poll_interval = 5  # seconds
        
        while True:
            elapsed_time = time.time() - start_time
            
            if elapsed_time > max_wait_seconds:
                logger.error(f"Research timed out after {max_wait_seconds} seconds")
                return "research failed"
            
            time.sleep(poll_interval)
            
            poll_response = requests.get(
                poll_url,
                headers={"x-api-key": api_key},
                timeout=30
            )
            
            if poll_response.status_code != 200:
                return "research failed"
            
            poll_data = poll_response.json()
            status = poll_data.get("status")
            
            #logger.info(f"Research {research_id} status: {status} (elapsed: {elapsed_time:.1f}s)")
            
            if status == "completed":
                # Extract result from output.content
                return poll_data.get("output", {}).get("content", "")
            
            elif status == "failed" or status == "canceled":
                return "research failed"
            
            elif status == "running" or status == "pending":
                # Continue polling
                continue
            
            else:
                # Unknown status
                return "research failed"
                
    except requests.exceptions.Timeout:
        logger.error("Request timeout during web research")
        return "research failed"
    except Exception as e:
        logger.error(f"Web research error: {str(e)}")
        return "research failed"
