import os
import argparse
import json
import time
import threading
import logging
from datetime import datetime
from crewai import LLM, Agent, Task, Crew, Process
from dotenv import load_dotenv
from tools import web_search_tool, get_webpage_content, update_research_plan
from app.config import logger

load_dotenv()

# Parse command-line arguments
parser = argparse.ArgumentParser(
    description="Deep Research System - Conduct comprehensive AI-powered research on any topic"
)
parser.add_argument(
    "query",
    type=str,
    nargs="?",
    default="Arkel.ai french company",
    help="Research query or topic to investigate (default: 'Arkel.ai french company')",
)
parser.add_argument(
    "--model",
    type=str,
    default="anthropic/claude-haiku-4.5",
    help="LLM model to use (default: claude-haiku-4.5)",
)
parser.add_argument(
    "--max-iter",
    type=int,
    default=50,
    help="Maximum iterations for the agent (default: 50)",
)
parser.add_argument(
    "--temperature",
    type=float,
    default=0.0,
    help="LLM temperature (default: 0.0)",
)
parser.add_argument(
    "--verbose",
    action="store_true",
    help="Enable verbose logging output",
)
parser.add_argument(
    "--provider",
    type=str,
    default=None,
    help="Specify provider(s) to use (e.g., 'cerebras', 'openai', 'anthropic'). Leave empty for automatic selection.",
)
parser.add_argument(
    "--reasoning",
    action="store_true",
    help="Enable reasoning mode (default: False)",
)

args = parser.parse_args()
query = args.query

# Clean up previous research plan to start fresh
plan_file = ".research_plan.json"
if os.path.exists(plan_file):
    try:
        os.remove(plan_file)
        logger.debug(f"Removed previous research plan: {plan_file}")
    except Exception as e:
        logger.warning(f"Could not remove previous research plan: {e}")

# Set logging level based on verbose flag
if args.verbose:
    logger.setLevel("DEBUG")
    logger.debug("Verbose logging enabled")
    # Enable third-party logs in verbose mode for debugging
    logging.getLogger("LiteLLM").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.INFO)
else:
    logger.setLevel("INFO")
    # Keep third-party logs suppressed in normal mode
    logging.getLogger("LiteLLM").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

# Log system configuration
logger.info(f"Deep Research System initialized - Query: '{query}'")
logger.info(
    f"Configuration: model={args.model}, max_iter={args.max_iter}, temperature={args.temperature}, provider={args.provider or 'auto'}"
)

# Display user-facing banner
print(f"\n{'=' * 60}")
print("🔍 Deep Research System")
print(f"{'=' * 60}")
print(f"Query: {query}")
print(f"Model: {args.model}")
print(f"Max Iterations: {args.max_iter}")
if args.provider:
    print(f"Provider: {args.provider}")
print(f"{'=' * 60}\n")

# Build LLM configuration with optional provider
extra_body = {}
if args.reasoning:
    extra_body["reasoning"] = {"max_tokens": 8192}
if args.provider:
    # Allow comma-separated providers for multiple options
    providers = [p.strip() for p in args.provider.split(",")]
    extra_body["provider"] = {"only": providers}
    logger.debug(f"Using provider(s): {providers}")

llm = LLM(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    model="openrouter/openrouter/" + args.model,
    temperature=args.temperature,
    extra_body=extra_body,
)

# Unified Deep Research Agent
research_agent = Agent(
    role="Deep Research Analyst",
    max_iter=args.max_iter,
    goal="Conduct thorough, comprehensive research on any topic by creating structured plans, gathering information from multiple sources, and synthesizing findings into well-formatted reports",
    backstory="""You are an AI research assistant with expertise in strategic planning, 
    information gathering, and technical writing. You excel at:
    
    **Planning & Strategy:**
    1. Breaking down complex queries into actionable research steps
    2. Creating structured TODO lists using the update_research_plan tool
    3. Prioritizing research areas and tracking progress
    
    **Research Execution:**
    4. Using web_search to find relevant sources quickly
    5. Using get_webpage_content to extract full content from specific URLs
    6. Cross-referencing information across multiple sources
    7. Documenting findings with proper citations
    8. Identifying contradictions and knowledge gaps
    
    **Report Writing:**
    9. Synthesizing complex findings into clear, structured reports
    10. Using markdown formatting (tables, bullet points, headers) for readability
    11. Maintaining objectivity while highlighting interesting insights
    12. Citing all sources with links
    
    You work systematically: create a plan, execute research step-by-step, update your 
    TODO list as you progress, and compile comprehensive reports with all findings.""",
    tools=[
        update_research_plan,
        web_search_tool,
        get_webpage_content,
    ],
    llm=llm,
    verbose=False,
)

# Deep Research Task - Unified workflow
research_task = Task(
    name="Deep Research Execution",
    description=f"""
    Conduct thorough, comprehensive research on the following topic:
    
    <research_task>
    {query}
    </research_task>
    
    Follow these instructions carefully:
    
    ## 1. Create Initial Research Plan
    
    Use the update_research_plan tool to create a TODO list outlining the main areas of 
    investigation. Break down the research into 10-15 specific, actionable steps.
    Before doing ANY research, you MUST create a COMPLETE TODO list 
    with ALL 10-15 items upfront, ALL with status "pending".
    
    **IMPORTANT**: You must pass a list of TODO dictionaries to the tool. Each TODO must have:
    - 'id': unique identifier (e.g., "step-1", "step-2", "step-3")
    - 'status': "pending" for initial plan items
    - 'content': Clear description of what needs to be investigated
    
    Example tool call:
    ```
    update_research_plan(
        todos=[
            {{"id": "step-1", "status": "pending", "content": "..."}},
            {{"id": "step-2", "status": "pending", "content": "..."}},
            {{"id": "step-3", "status": "pending", "content": "..."}},
            ... // continue with ALL items "pending"
        ],
        explanation="Creating initial research plan for {query}"
    )
    ```
    
    ## 2. Conduct Web Research
    
    In deep research mode, ALL information presented must come from verified sources:
    - Use web_search to find relevant sources for each TODO item
    - Use get_webpage_content to extract full content from specific URLs you found
    - Before using any tool, provide your reasoning for that choice
    - Collect all necessary data concisely and thoroughly
    - Gather data from multiple sources to ensure accuracy
    - Update your TODO list status as you progress
    
    **Updating TODO status**: When you start working on a TODO, mark it as "in_progress":
    ```
    update_research_plan(
        todos=[{{"id": "step-1", "status": "in_progress"}}],
        explanation="Starting research on company background"
    )
    ```
    
    When you finish a TODO, mark it as "completed":
    ```
    update_research_plan(
        todos=[{{"id": "step-1", "status": "completed"}}],
        explanation="Completed research on company background"
    )
    ```
    
    ## 3. Information Gathering Guidelines
    
    - Use bullet points or numbered lists for clarity when appropriate
    - Don't ask for unnecessary information or information already provided
    - Continue researching until all items in your TODO list are completed
    - Use available tools one at a time to find the requested information
    - Cross-reference information across multiple sources
    
    ## 4. Citation Requirements
    
    Cite all sources used with links to the original websites throughout your research.
    
    ## 5. Compile Final Report
    
    Once you have gathered all information, compile a comprehensive report using markdown 
    formatting. Your report must include:
    
    **[Title of Report]**
    
    [Include your comprehensive report here with appropriate formatting:
    - Use headers (##, ###) to organize sections
    - Use bullet points and numbered lists for clarity
    - Include tables where appropriate
    - Present findings with supporting evidence
    - Maintain professional, objective tone]
    
    **Interesting Findings:**
    [Highlight any surprising or noteworthy details you discovered during your research]
    
    **Sources:**
    [List all sources with links in a clear format]
    
    ## Key Principles:
    
    - Be systematic: plan → research → update status → compile
    - Be thorough: multiple sources, cross-verification
    - Be transparent: cite everything, acknowledge gaps
    - Be clear: well-structured, readable format
    """,
    agent=research_agent,
    expected_output="""A comprehensive research report in markdown format containing:
    
    1. **Well-Structured Report**
       - Clear title and introduction
       - Logical organization with headers and subheaders
       - Detailed findings with supporting evidence
       - Professional presentation using markdown formatting
    
    2. **Interesting Findings Section**
       - Surprising or noteworthy discoveries
       - Unique insights from the research
    
    3. **Complete Source List**
       - All sources cited with working URLs
       - Organized and easy to reference
    
    4. **Research Quality**
       - Information from multiple verified sources
       - Cross-referenced and validated data
       - Balanced presentation of different perspectives
       - Acknowledgment of any limitations or gaps
    
    The report should be immediately useful, thoroughly researched, and professionally 
    presented.""",
)

# Crew assembly
crew = Crew(
    name="Deep Research Crew",
    agents=[research_agent],
    tasks=[research_task],
    verbose=False,
    process=Process.sequential,
)


# Plan monitoring function
def monitor_plan():
    """Monitor and display research plan updates in real-time"""
    plan_file = ".research_plan.json"
    last_content = None
    first_render = True

    logger.info("Starting real-time plan monitoring")
    print("\n📋 Research Plan Monitor")
    print("=" * 60)

    # Save cursor position after header
    print("\033[s", end="", flush=True)

    while monitoring:
        try:
            if os.path.exists(plan_file):
                with open(plan_file, "r") as f:
                    content = f.read()

                if content != last_content and content.strip():
                    last_content = content
                    data = json.loads(content)

                    todos = data.get("todos", [])
                    if todos:
                        # Count by status
                        status_counts = {}
                        for todo in todos:
                            status = todo.get("status", "unknown")
                            status_counts[status] = status_counts.get(status, 0) + 1

                        # Status emojis
                        status_emoji = {
                            "pending": "⏳",
                            "in_progress": "🔄",
                            "completed": "✅",
                            "cancelled": "❌",
                        }

                        # Restore cursor position and clear below
                        if not first_render:
                            print("\033[u", end="")  # Restore cursor
                            print("\033[J", end="")  # Clear from cursor to end
                        first_render = False

                        # Build the display
                        display_lines = []
                        display_lines.append(f"\n📊 Progress: {len(todos)} tasks total")

                        for status, count in sorted(
                            status_counts.items(),
                            key=lambda x: [
                                "in_progress",
                                "pending",
                                "completed",
                                "cancelled",
                            ].index(x[0])
                            if x[0]
                            in ["in_progress", "pending", "completed", "cancelled"]
                            else 999,
                        ):
                            emoji = status_emoji.get(status, "❓")
                            display_lines.append(f"   {emoji} {status}: {count}")

                        display_lines.append("\n📋 Current Plan:")
                        for i, todo in enumerate(todos, 1):
                            status = todo.get("status", "unknown")
                            emoji = status_emoji.get(status, "❓")
                            todo_content = todo.get("content", "No content")
                            # Truncate long content for display
                            if len(todo_content) > 70:
                                todo_content = todo_content[:67] + "..."
                            display_lines.append(
                                f"   {i:2}. {emoji} [{status:12}] {todo_content}"
                            )

                        display_lines.append("=" * 60)

                        # Print all lines at once
                        print("\n".join(display_lines), flush=True)

            time.sleep(2)  # Check every 2 seconds

        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error in plan monitor: {e}")
            pass
        except Exception as e:
            logger.error(f"Error in plan monitoring: {e}")
            pass


# Start plan monitoring in background
monitoring = True
monitor_thread = threading.Thread(target=monitor_plan, daemon=True)
monitor_thread.start()
logger.info("Plan monitoring thread started")

print("\n🚀 Starting Deep Research...")
print("=" * 60)

try:
    # Execute research
    logger.info("Starting research execution")
    result = crew.kickoff()
    logger.info("Research execution completed successfully")
except Exception as e:
    logger.error(f"Research execution failed: {e}")
    monitoring = False
    raise
finally:
    # Stop monitoring
    monitoring = False
    time.sleep(0.5)  # Give monitor thread time to finish
    logger.info("Plan monitoring stopped")

# Display final result
logger.info("Displaying final research report")
print("\n\n" + "=" * 60)
print("✨ RESEARCH COMPLETED")
print("=" * 60)
print("\n📄 Final Report:\n")
print(result)
print("\n" + "=" * 60)
completion_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
print(f"✅ Research completed at {completion_time}")
print("=" * 60)
logger.info(f"Research session completed at {completion_time}")
