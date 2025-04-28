from typing import Any, List, Dict, Optional
import asyncio
import click
import httpx
from mcp.server.fastmcp import FastMCP
import time

# Initialize FastMCP server
mcp = FastMCP("browser-use")

# Constants
BROWSER_USE_API_BASE = "https://api.browser-use.com/api/v1"
# Global variable to store the API key
BROWSER_USE_API_KEY = None

class BrowserUseTaskData:
    def __init__(
        self, 
        id: str, 
        status: str, 
        steps: List[Dict[str, Any]], 
        output: Any
    ):
        self.id = id
        self.status = status
        self.steps = steps
        self.output = output

    def to_text(self) -> str:
        steps_text = "\n".join(
            [f"Step {i+1}: {step.get('title', 'Unknown')}" for i, step in enumerate(self.steps)])
        
        output_text = str(self.output) if self.output else "No output available"
        
        return f"""
            Task ID: {self.id}
            Status: {self.status}
            Steps:
            {steps_text}

            Output:
            {output_text}
        """

async def make_browser_use_request(
    method: str,
    path: str,
    json_data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Make a request to the Browser Use API with proper error handling."""
    if not BROWSER_USE_API_KEY:
        return {"error": "API key not provided. Please provide --api-key argument."}
    
    headers = {
        "Authorization": f"Bearer {BROWSER_USE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    url = f"{BROWSER_USE_API_BASE}{path}"
    
    async with httpx.AsyncClient() as client:
        try:
            if method.lower() == "get":
                response = await client.get(url, headers=headers, timeout=30.0)
            elif method.lower() == "post":
                response = await client.post(url, headers=headers, json=json_data, timeout=30.0)
            elif method.lower() == "put":
                response = await client.put(url, headers=headers, json=json_data, timeout=30.0)
            else:
                return {"error": f"Unsupported method: {method}"}
            
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            return {"error": f"API request failed: {e}"}
        except Exception as e:
            return {"error": f"Request failed: {e}"}

@mcp.tool("run_task")
async def run_task(
    instructions: str, 
    structured_output: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    """Run a Browser Use automation task with instructions and wait for completion.
    
    Args:
        instructions: Instructions for the browser automation task
        structured_output: JSON schema for structured output (optional)
        parameters: Additional parameters for the task (optional)
        
    Returns:
        Information about the created task including final output if wait_for_completion is True
    """
    wait_for_completion = True
    timeout_seconds = 300
    # Validate required parameters
    if not instructions:
        return [{"type": "text", "text": "Error: Missing task instructions. Please provide instructions for what the browser should do."}]
    
    payload = {"task": instructions}
    
    if structured_output:
        payload["structured_output_json"] = structured_output
        
    if parameters:
        payload.update(parameters)
    
    result = await make_browser_use_request("post", "/run-task", payload)
    
    if "error" in result:
        return [{"type": "text", "text": f"Error: {result['error']}"}]
    task_id = result.get("id", "unknown")
    task = BrowserUseTaskData(
        id=task_id,
        status="running",
        steps=[],
        output=None
    )

    try:
        if not wait_for_completion:
            return [{"type": "text", "text": f"Task started with ID: {task_id}\n\n{task.to_text()}"}]
        
        # Poll task status until completion or timeout
        
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            # Get latest task status
            task_result = await make_browser_use_request("get", f"/task/{task_id}")

            if "error" in task_result:
                return [{"type": "text", "text": f"Error checking task status: {task_result['error']}"}]
            
            status = task_result.get("status", "unknown")
                
            # If task is no longer running, return the final result
            if status not in ["running", "created"]:
                task = BrowserUseTaskData(
                    id=task_id,
                    status=status,
                    steps=task_result.get("steps", []),
                    output=task_result.get("output")
                )
                return [{"type": "text", "text": f"Task completed with status: {status}\n\n{task.to_text()}"}]
            
            # Wait before checking again
            await asyncio.sleep(1)
        
        # If we get here, task timed out
        return [{"type": "text", "text": f"Task is taking longer than {timeout_seconds} seconds. Task ID: {task_id}, current status: {task.status}\n\n{task.to_text()}"}]
            
    except Exception as e:
        return [{"type": "text", "text": f"Error processing task: {e}\nAPI response: {result}"}]

@mcp.tool("get_task")
async def get_task(task_id: str) -> List[Dict[str, str]]:
    """Get details of a Browser Use task by ID.
    
    Args:
        task_id: ID of the task to retrieve
        
    Returns:
        Complete task information including steps and output
    """
    # Validate required parameters
    if not task_id:
        return [{"type": "text", "text": "Error: Missing task_id. Please provide the ID of the task you want to retrieve."}]
    
    result = await make_browser_use_request("get", f"/task/{task_id}")
    
    if "error" in result:
        return [{"type": "text", "text": f"Error: {result['error']}"}]
    
    try:
        task = BrowserUseTaskData(
            id=result.get("id", task_id),
            status=result.get("status", "unknown"),
            steps=result.get("steps", []),
            output=result.get("output")
        )
        
        return [{"type": "text", "text": task.to_text()}]
    except Exception as e:
        return [{"type": "text", "text": f"Error processing task data: {e}\nAPI response: {result}"}]

@mcp.tool("get_task_status")
async def get_task_status(task_id: str) -> List[Dict[str, str]]:
    """Get the status of a Browser Use task.
    
    Args:
        task_id: ID of the task to check
        
    Returns:
        Current status of the task
    """
    # Validate required parameters
    if not task_id:
        return [{"type": "text", "text": "Error: Missing task_id. Please provide the ID of the task you want to check."}]
    
    result = await make_browser_use_request("get", f"/task/{task_id}/status")
    
    if "error" in result:
        return [{"type": "text", "text": f"Error: {result['error']}"}]
    
    return [{"type": "text", "text": f"Task status: {result}"}]

@mcp.tool("stop_task")
async def stop_task(task_id: str) -> List[Dict[str, str]]:
    """Stop a running Browser Use task.
    
    Args:
        task_id: ID of the task to stop
        
    Returns:
        Confirmation of task being stopped
    """
    # Validate required parameters
    if not task_id:
        return [{"type": "text", "text": "Error: Missing task_id. Please provide the ID of the task you want to stop."}]
    
    result = await make_browser_use_request("put", f"/stop-task?task_id={task_id}")
    
    if "error" in result:
        return [{"type": "text", "text": f"Error: {result['error']}"}]
    
    return [{"type": "text", "text": "Task stopped successfully"}]

@mcp.tool("pause_task")
async def pause_task(task_id: str) -> List[Dict[str, str]]:
    """Pause a running Browser Use task.
    
    Args:
        task_id: ID of the task to pause
        
    Returns:
        Confirmation of task being paused
    """
    # Validate required parameters
    if not task_id:
        return [{"type": "text", "text": "Error: Missing task_id. Please provide the ID of the task you want to pause."}]
    
    result = await make_browser_use_request("put", f"/pause-task?task_id={task_id}")
    
    if "error" in result:
        return [{"type": "text", "text": f"Error: {result['error']}"}]
    
    return [{"type": "text", "text": "Task paused successfully"}]

@mcp.tool("resume_task")
async def resume_task(task_id: str) -> List[Dict[str, str]]:
    """Resume a paused Browser Use task.
    
    Args:
        task_id: ID of the task to resume
        
    Returns:
        Confirmation of task being resumed
    """
    # Validate required parameters
    if not task_id:
        return [{"type": "text", "text": "Error: Missing task_id. Please provide the ID of the task you want to resume."}]
    
    result = await make_browser_use_request("put", f"/resume-task?task_id={task_id}")
    
    if "error" in result:
        return [{"type": "text", "text": f"Error: {result['error']}"}]
    
    return [{"type": "text", "text": "Task resumed successfully"}]

@mcp.tool("list_tasks")
async def list_tasks() -> List[Dict[str, str]]:
    """List all Browser Use tasks.
    
    Returns:
        List of all tasks with their IDs and statuses
    """
    result = await make_browser_use_request("get", "/tasks")
    
    if "error" in result:
        return [{"type": "text", "text": f"Error: {result['error']}"}]
    
    if not result or not isinstance(result, list):
        return [{"type": "text", "text": "No tasks found or invalid response format"}]
    
    try:
        tasks_text = "\n".join([f"Task ID: {task.get('id', 'unknown')}, Status: {task.get('status', 'unknown')}" for task in result])
        return [{"type": "text", "text": f"Browser Use Tasks:\n{tasks_text}" if tasks_text else "No tasks found"}]
    except Exception as e:
        return [{"type": "text", "text": f"Error processing tasks: {e}\nAPI response: {result}"}]

@mcp.tool("check_balance")
async def check_balance() -> List[Dict[str, str]]:
    """Check your Browser Use account balance.
    
    Returns:
        Account balance information
    """
    result = await make_browser_use_request("get", "/balance")
    
    if "error" in result:
        return [{"type": "text", "text": f"Error: {result['error']}"}]
    
    try:
        return [{"type": "text", "text": f"Balance: {result}"}]
    except Exception as e:
        return [{"type": "text", "text": f"Error processing balance data: {e}\nAPI response: {result}"}]

@mcp.prompt("browser-use-task")
async def browser_use_task(
    instructions: str, 
    structured_output: Optional[str] = None
) -> Dict[str, Any]:
    """Run a Browser Use automation task.
    
    Args:
        instructions: Instructions for the browser automation task
        structured_output: JSON schema for structured output (optional)
        
    Returns:
        A prompt result with task details
    """
    # Validate required parameters
    if not instructions:
        return {
            "description": "Error: Missing instructions",
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": "Error: Missing task instructions. Please provide instructions for what the browser should do."}]}
            ]
        }
    
    payload = {"task": instructions}
    
    if structured_output:
        payload["structured_output_json"] = structured_output
    
    result = await make_browser_use_request("post", "/run-task", payload)
    
    if "error" in result:
        return {
            "description": f"Error running task",
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": f"Error: {result['error']}"}]}
            ]
        }
    
    try:
        task = BrowserUseTaskData(
            id=result.get("id", "unknown"),
            status="running",
            steps=[],
            output=None
        )
        
        return {
            "description": f"Browser Use Task: {task.id}",
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": task.to_text()}]}
            ]
        }
    except Exception as e:
        return {
            "description": "Error processing task",
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": f"Error creating task: {e}\nAPI response: {result}"}]}
            ]
        }

@click.command()
@click.option(
    "--api-key",
    envvar="BROWSER_USE_API_KEY",
    required=True,
    help="Browser Use API key",
)
def main(api_key: str):
    """Run the Browser Use MCP server."""
    global BROWSER_USE_API_KEY
    BROWSER_USE_API_KEY = api_key
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()
