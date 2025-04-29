from typing import Any, List, Dict, Optional
import asyncio
import click
import httpx
import time
import enum
import logging
import textwrap
from pydantic import BaseModel
from mcp.server.fastmcp import FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("browser-use-mcp")

# Initialize FastMCP server
mcp = FastMCP("browser_use")

# Pydantic models for tool and prompt definitions
class ToolDefinition(BaseModel):
    """Definition of an MCP tool with name and description."""
    name: str
    description: str

class PromptDefinition(BaseModel):
    """Definition of an MCP prompt with name and description."""
    name: str
    description: str

# Constants
class Config:
    """Configuration constants for the Browser Use MCP server."""
    API_BASE = "https://api.browser-use.com/api/v1"
    REQUEST_TIMEOUT = 30.0
    TASK_POLL_INTERVAL = 1.0
    TASK_TIMEOUT = 300  # 5 minutes

# Enums
class TaskStatus(enum.Enum):
    """Enumeration of possible task statuses."""
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"
    PAUSED = "paused"
    UNKNOWN = "unknown"
    
    @classmethod
    def is_active(cls, status: str) -> bool:
        """Check if a task status indicates the task is still running."""
        return status in [cls.CREATED.value, cls.RUNNING.value]

class HttpMethod(enum.Enum):
    """Enumeration of HTTP methods used in API requests."""
    GET = "get"
    POST = "post"
    PUT = "put"

class Tool(enum.Enum):
    """Enumeration of MCP tool definitions."""
    RUN_TASK = ToolDefinition(
        name="run_task",
        description=textwrap.dedent("""
            Run a browser automation task with instructions and wait for completion.
            Returns the task's final output when complete.
        """).strip()
    )
    GET_TASK = ToolDefinition(
        name="get_task",
        description=textwrap.dedent("""
            Retrieve details of a browser automation task by its ID, including steps and output.
        """).strip()
    )
    GET_TASK_STATUS = ToolDefinition(
        name="get_task_status",
        description=textwrap.dedent("""
            Check the current status of a browser automation task without retrieving full details.
        """).strip()
    )
    STOP_TASK = ToolDefinition(
        name="stop_task",
        description=textwrap.dedent("""
            Stop a running browser automation task. A stopped task cannot be resumed.
        """).strip()
    )
    PAUSE_TASK = ToolDefinition(
        name="pause_task",
        description=textwrap.dedent("""
            Pause a running browser automation task so it can be resumed later using the resume_task tool.
        """).strip()
    )
    RESUME_TASK = ToolDefinition(
        name="resume_task",
        description=textwrap.dedent("""
            Resume a previously paused browser automation task to continue execution from where it left off.
        """).strip()
    )
    LIST_TASKS = ToolDefinition(
        name="list_tasks",
        description=textwrap.dedent("""
            List all browser automation tasks in your account with their current status.
            Use get_task to retrieve full details for a specific task.
        """).strip()
    )
    CHECK_BALANCE = ToolDefinition(
        name="check_balance",
        description=textwrap.dedent("""
            Check your Browser Use account balance, usage limits, and available credits.
        """).strip()
    )

class PromptName(enum.Enum):
    """Enumeration of MCP prompt definitions."""
    BROWSER_USE_TASK = PromptDefinition(
        name="browser_use_task",
        description=textwrap.dedent("""
            Run a Browser Use automation task and receive structured information about steps and results
            as a conversational context for the AI.
        """).strip()
    )

# Error handling
class BrowserUseApiError(Exception):
    """Exception raised for errors in the Browser Use API."""
    def __init__(self, message: str, response: Optional[httpx.Response] = None):
        self.message = message
        self.response = response
        super().__init__(self.message)

# Data models
class BrowserUseTaskData:
    """Model representing a Browser Use task."""
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
        """Format task data as human-readable text."""
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

# API client
class BrowserUseApiClient:
    """Client for interacting with the Browser Use API."""
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = Config.API_BASE
        
    def _get_headers(self) -> Dict[str, str]:
        """Get the headers for API requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    async def request(
        self,
        method: HttpMethod,
        path: str,
        json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make a request to the Browser Use API with error handling."""
        if not self.api_key:
            raise BrowserUseApiError("API key not provided. Please provide --api-key argument.")
        
        url = f"{self.base_url}{path}"
        
        async with httpx.AsyncClient() as client:
            try:
                if method == HttpMethod.GET:
                    response = await client.get(url, headers=self._get_headers(), timeout=Config.REQUEST_TIMEOUT)
                elif method == HttpMethod.POST:
                    response = await client.post(url, headers=self._get_headers(), json=json_data, timeout=Config.REQUEST_TIMEOUT)
                elif method == HttpMethod.PUT:
                    response = await client.put(url, headers=self._get_headers(), json=json_data, timeout=Config.REQUEST_TIMEOUT)
                else:
                    raise BrowserUseApiError(f"Unsupported method: {method}")
                
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"API request failed: {e}")
                raise BrowserUseApiError(f"API request failed: {e}", response=e.response)
            except Exception as e:
                logger.error(f"Request failed: {e}")
                raise BrowserUseApiError(f"Request failed: {e}")
    
    async def run_task(self, instructions: str, structured_output: Optional[str] = None, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a new browser automation task."""
        payload = {"task": instructions}
        
        if structured_output:
            payload["structured_output_json"] = structured_output
            
        if parameters:
            payload.update(parameters)
            
        return await self.request(HttpMethod.POST, "/run-task", payload)
    
    async def get_task(self, task_id: str) -> Dict[str, Any]:
        """Get details of a task by ID."""
        return await self.request(HttpMethod.GET, f"/task/{task_id}")
    
    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get the status of a task."""
        return await self.request(HttpMethod.GET, f"/task/{task_id}/status")
    
    async def stop_task(self, task_id: str) -> Dict[str, Any]:
        """Stop a running task."""
        return await self.request(HttpMethod.PUT, f"/stop-task?task_id={task_id}")
    
    async def pause_task(self, task_id: str) -> Dict[str, Any]:
        """Pause a running task."""
        return await self.request(HttpMethod.PUT, f"/pause-task?task_id={task_id}")
    
    async def resume_task(self, task_id: str) -> Dict[str, Any]:
        """Resume a paused task."""
        return await self.request(HttpMethod.PUT, f"/resume-task?task_id={task_id}")
    
    async def list_tasks(self) -> List[Dict[str, Any]]:
        """List all tasks."""
        return await self.request(HttpMethod.GET, "/tasks")
    
    async def check_balance(self) -> Dict[str, Any]:
        """Check account balance."""
        return await self.request(HttpMethod.GET, "/balance")

# Service layer
class BrowserUseService:
    """Service for managing Browser Use tasks."""
    def __init__(self, client: BrowserUseApiClient):
        self.client = client
    
    async def run_task_with_polling(
        self, 
        instructions: str, 
        structured_output: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        wait_for_completion: bool = True,
        timeout_seconds: int = Config.TASK_TIMEOUT
    ) -> BrowserUseTaskData:
        """Run a Browser Use task and optionally wait for completion."""
        try:
            # Start the task
            result = await self.client.run_task(instructions, structured_output, parameters)
            task_id = result.get("id", "unknown")
            
            task = BrowserUseTaskData(
                id=task_id,
                status=TaskStatus.RUNNING.value,
                steps=[],
                output=None
            )
            
            # If not waiting for completion, return immediately
            if not wait_for_completion:
                return task
            
            # Poll task status until completion or timeout
            task = await self._poll_task_until_completion(task_id, timeout_seconds)
            return task
            
        except BrowserUseApiError as e:
            logger.error(f"Error running task: {e.message}")
            raise
    
    async def _poll_task_until_completion(self, task_id: str, timeout_seconds: int) -> BrowserUseTaskData:
        """Poll a task's status until it completes or times out."""
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            try:
                # Get latest task status
                task_result = await self.client.get_task(task_id)
                
                status = task_result.get("status", TaskStatus.UNKNOWN.value)
                
                # If task is no longer running, return the final result
                if not TaskStatus.is_active(status):
                    return BrowserUseTaskData(
                        id=task_id,
                        status=status,
                        steps=task_result.get("steps", []),
                        output=task_result.get("output")
                    )
                
                # Wait before checking again
                await asyncio.sleep(Config.TASK_POLL_INTERVAL)
                
            except BrowserUseApiError as e:
                logger.error(f"Error checking task status: {e.message}")
                raise
        
        # If we get here, task timed out
        return BrowserUseTaskData(
            id=task_id,
            status="timeout",
            steps=[],
            output=None
        )

# Global API client and service instances
api_client = None
browser_use_service = None

# Tool implementations
@mcp.tool(
    name=Tool.RUN_TASK.value.name,
    description=Tool.RUN_TASK.value.description
)
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
    # Validate required parameters
    if not instructions:
        return [{"type": "text", "text": "Error: Missing task instructions. Please provide instructions for what the browser should do."}]
    
    try:
        task = await browser_use_service.run_task_with_polling(
            instructions, 
            structured_output, 
            parameters
        )
        
        return [{"type": "text", "text": f"Task completed with status: {task.status}\n\n{task.to_text()}"}]
    except BrowserUseApiError as e:
        return [{"type": "text", "text": f"Error: {e.message}"}]
    except Exception as e:
        logger.exception("Unexpected error in run_task")
        return [{"type": "text", "text": f"Error processing task: {str(e)}"}]

@mcp.tool(
    name=Tool.GET_TASK.value.name,
    description=Tool.GET_TASK.value.description
)
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
    
    try:
        result = await api_client.get_task(task_id)
        
        task = BrowserUseTaskData(
            id=result.get("id", task_id),
            status=result.get("status", TaskStatus.UNKNOWN.value),
            steps=result.get("steps", []),
            output=result.get("output")
        )
        
        return [{"type": "text", "text": task.to_text()}]
    except BrowserUseApiError as e:
        return [{"type": "text", "text": f"Error: {e.message}"}]
    except Exception as e:
        logger.exception("Unexpected error in get_task")
        return [{"type": "text", "text": f"Error processing task data: {str(e)}"}]

@mcp.tool(
    name=Tool.GET_TASK_STATUS.value.name,
    description=Tool.GET_TASK_STATUS.value.description
)
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
    
    try:
        result = await api_client.get_task_status(task_id)
        return [{"type": "text", "text": f"Task status: {result}"}]
    except BrowserUseApiError as e:
        return [{"type": "text", "text": f"Error: {e.message}"}]
    except Exception as e:
        logger.exception("Unexpected error in get_task_status")
        return [{"type": "text", "text": f"Error checking task status: {str(e)}"}]

@mcp.tool(
    name=Tool.STOP_TASK.value.name,
    description=Tool.STOP_TASK.value.description
)
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
    
    try:
        await api_client.stop_task(task_id)
        return [{"type": "text", "text": "Task stopped successfully"}]
    except BrowserUseApiError as e:
        return [{"type": "text", "text": f"Error: {e.message}"}]
    except Exception as e:
        logger.exception("Unexpected error in stop_task")
        return [{"type": "text", "text": f"Error stopping task: {str(e)}"}]

@mcp.tool(
    name=Tool.PAUSE_TASK.value.name,
    description=Tool.PAUSE_TASK.value.description
)
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
    
    try:
        await api_client.pause_task(task_id)
        return [{"type": "text", "text": "Task paused successfully"}]
    except BrowserUseApiError as e:
        return [{"type": "text", "text": f"Error: {e.message}"}]
    except Exception as e:
        logger.exception("Unexpected error in pause_task")
        return [{"type": "text", "text": f"Error pausing task: {str(e)}"}]

@mcp.tool(
    name=Tool.RESUME_TASK.value.name,
    description=Tool.RESUME_TASK.value.description
)
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
    
    try:
        await api_client.resume_task(task_id)
        return [{"type": "text", "text": "Task resumed successfully"}]
    except BrowserUseApiError as e:
        return [{"type": "text", "text": f"Error: {e.message}"}]
    except Exception as e:
        logger.exception("Unexpected error in resume_task")
        return [{"type": "text", "text": f"Error resuming task: {str(e)}"}]

@mcp.tool(
    name=Tool.LIST_TASKS.value.name,
    description=Tool.LIST_TASKS.value.description
)
async def list_tasks() -> List[Dict[str, str]]:
    """List all Browser Use tasks.
    
    Returns:
        List of all tasks with their IDs and statuses
    """
    try:
        result = await api_client.list_tasks()
        
        if not result or not isinstance(result, list):
            return [{"type": "text", "text": "No tasks found or invalid response format"}]
        
        tasks_text = "\n".join([f"Task ID: {task.get('id', 'unknown')}, Status: {task.get('status', 'unknown')}" for task in result])
        return [{"type": "text", "text": f"Browser Use Tasks:\n{tasks_text}" if tasks_text else "No tasks found"}]
    except BrowserUseApiError as e:
        return [{"type": "text", "text": f"Error: {e.message}"}]
    except Exception as e:
        logger.exception("Unexpected error in list_tasks")
        return [{"type": "text", "text": f"Error listing tasks: {str(e)}"}]

@mcp.tool(
    name=Tool.CHECK_BALANCE.value.name,
    description=Tool.CHECK_BALANCE.value.description
)
async def check_balance() -> List[Dict[str, str]]:
    """Check your Browser Use account balance.
    
    Returns:
        Account balance information
    """
    try:
        result = await api_client.check_balance()
        return [{"type": "text", "text": f"Balance: {result}"}]
    except BrowserUseApiError as e:
        return [{"type": "text", "text": f"Error: {e.message}"}]
    except Exception as e:
        logger.exception("Unexpected error in check_balance")
        return [{"type": "text", "text": f"Error checking balance: {str(e)}"}]

@mcp.prompt(
    name=PromptName.BROWSER_USE_TASK.value.name,
    description=PromptName.BROWSER_USE_TASK.value.description
)
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
    
    try:
        task = await browser_use_service.run_task_with_polling(
            instructions, 
            structured_output,
            wait_for_completion=False
        )
        
        return {
            "description": f"Browser Use Task: {task.id}",
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": task.to_text()}]}
            ]
        }
    except BrowserUseApiError as e:
        return {
            "description": f"Error running task",
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": f"Error: {e.message}"}]}
            ]
        }
    except Exception as e:
        logger.exception("Unexpected error in browser_use_task prompt")
        return {
            "description": "Error processing task",
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": f"Error creating task: {str(e)}"}]}
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
    global api_client, browser_use_service
    
    try:
        # Initialize API client
        api_client = BrowserUseApiClient(api_key)
        
        # Initialize service
        browser_use_service = BrowserUseService(api_client)
        
        logger.info("Starting Browser Use MCP server")
        
        # Run the MCP server
        mcp.run(transport="stdio")
    except Exception as e:
        logger.exception(f"Failed to start Browser Use MCP server: {str(e)}")
        raise

if __name__ == "__main__":
    main()
