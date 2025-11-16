"""Web research tool using Exa AI Research API"""

import os
import json
import time
import requests
from crewai.tools import tool
from pydantic import Field

try:
    from app.config import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

@tool("update_research_plan")
def update_research_plan(
    todos: list[dict] = Field(
        ...,
        description="""Array of TODO items. Each item must have:
        - 'id': unique identifier (e.g., 'step-1', 'step-2')
        - 'status': one of 'pending', 'in_progress', 'completed', or 'cancelled'
        - 'content': description of the task
        
        Example: [{"id": "step-1", "status": "pending", "content": "Research company background"}]
        """,
        min_length=1,
    ),
    explanation: str = Field(
        default="",
        description="Short description of the action (e.g., 'Creating initial plan', 'Completed step 1')",
    ),
) -> str:
    """Create and manage a structured TODO list for research sessions.
    
    This tool persists TODOs to a JSON file. When updating existing TODOs, only provide
    the fields you want to change - the tool will merge with existing data.
    
    Example usage:
    - Create initial plan: Pass 5-10 TODO items with status 'pending'
    - Mark item in progress: Pass the item with status 'in_progress'
    - Complete item: Pass the item with status 'completed'
    """
    
    # Validate input
    if not todos or len(todos) == 0:
        error_msg = "Cannot update research plan: todos list is empty. You must provide at least one TODO item."
        logger.error(error_msg)
        return error_msg
    
    # Define storage location
    storage_file = os.path.join(os.getcwd(), ".research_plan.json")
    
    # Load existing TODOs
    existing_todos = {}
    if os.path.exists(storage_file):
        try:
            with open(storage_file, "r") as f:
                data = json.load(f)
                existing_todos = {todo["id"]: todo for todo in data.get("todos", [])}
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to load existing research plan: {e}")
            existing_todos = {}
    
    # Merge new TODOs with existing ones
    for todo in todos:
        todo_id = todo.get("id")
        if not todo_id:
            logger.warning("Skipping TODO without ID")
            continue
            
        if todo_id in existing_todos:
            # Update existing TODO (merge fields)
            existing_todos[todo_id].update({
                k: v for k, v in todo.items() if v is not None
            })
        else:
            # Add new TODO
            existing_todos[todo_id] = {
                "id": todo_id,
                "status": todo.get("status", "pending"),
                "content": todo.get("content", ""),
            }
    
    # Convert back to list and sort by status priority
    status_priority = {"in_progress": 0, "pending": 1, "completed": 2, "cancelled": 3}
    todo_list = sorted(
        existing_todos.values(),
        key=lambda x: status_priority.get(x.get("status", "pending"), 999)
    )
    
    # Save to file
    try:
        with open(storage_file, "w") as f:
            json.dump({
                "explanation": explanation,
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "todos": todo_list
            }, f, indent=2)
        
        
        # Build summary
        status_counts = {}
        for todo in todo_list:
            status = todo.get("status", "pending")
            status_counts[status] = status_counts.get(status, 0) + 1
        
        summary = f"Research plan updated successfully. {explanation}\n"
        summary += f"Total TODOs: {len(todo_list)} ("
        summary += ", ".join([f"{count} {status}" for status, count in status_counts.items()])
        summary += ")"
        
        return summary
        
    except Exception as e:
        error_msg = f"Failed to save research plan: {str(e)}"
        logger.error(error_msg)
        return error_msg
