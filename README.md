# Browser Use MCP server

[![smithery badge](https://smithery.ai/badge/@mhazarabad/browser-use-mcp)](https://smithery.ai/server/@mhazarabad/browser-use-mcp)

## Overview

A Model Context Protocol server for automating browser tasks using Browser Use API. This server provides tools to run browser automation tasks, monitor task status, and manage running tasks.

## Prerequisites

- A Browser Use API key

to get a Browser Use API key, go to [Cloud Browser Use](https://cloud.browser-use.com/) and sign up.

## Installation

### Installing via Smithery

To install browser-use-mcp for Claude Desktop automatically via [Smithery](https://smithery.ai/server/@mhazarabad/browser-use-mcp):

```bash
npx -y @smithery/cli install @mhazarabad/browser-use-mcp --client claude
```

The package is not published to PyPI. You'll need to clone this repository and run it directly from source.

```
git clone https://github.com/mhazarabad/browser-use-mcp.git
cd browser-use-mcp
```

## Running the Server

### Using Python directly

```bash
python /path/to/browser-use-mcp/src/server.py --api-key YOUR_BROWSER_USE_API_KEY
```

### Using uvx (recommended)

First, install [uv](https://github.com/astral-sh/uv) if you haven't already:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then you can run the server using uvx:

```bash
uvx run /path/to/browser-use-mcp/src/server.py --api-key YOUR_BROWSER_USE_API_KEY
```

Or, for development purposes, you can use:

```bash
uv run /path/to/browser-use-mcp/src/server.py --api-key YOUR_BROWSER_USE_API_KEY
```

## Tools

1. `run task`
   - Run a Browser Use automation task with instructions and wait for completion
   - Input:
     - `instructions` (string): Instructions for the browser automation task
     - `structured_output` (string, optional): JSON schema for structured output
     - `parameters` (object, optional): Additional parameters for the task
   - Returns: Information about the created task including final output if wait_for_completion is True

2. `get task`
   - Get details of a Browser Use task by ID
   - Input:
     - `task_id` (string): ID of the task to retrieve
   - Returns: Complete task information including steps and output

3. `get task status`
   - Get the status of a Browser Use task
   - Input:
     - `task_id` (string): ID of the task to check
   - Returns: Current status of the task

4. `stop task`
   - Stop a running Browser Use task
   - Input:
     - `task_id` (string): ID of the task to stop
   - Returns: Confirmation of task being stopped

5. `pause task`
   - Pause a running Browser Use task
   - Input:
     - `task_id` (string): ID of the task to pause
   - Returns: Confirmation of task being paused

6. `resume task`
   - Resume a paused Browser Use task
   - Input:
     - `task_id` (string): ID of the task to resume
   - Returns: Confirmation of task being resumed

7. `list tasks`
   - List all Browser Use tasks
   - Returns: List of all tasks with their IDs and statuses

8. `check balance`
   - Check your Browser Use account balance
   - Returns: Account balance information

### Prompts

1. `browser-use-task`
   - Run a Browser Use automation task
   - Input:
     - `instructions` (string): Instructions for the browser automation task
     - `structured_output` (string, optional): JSON schema for structured output
   - Returns: Formatted task details as conversation context

## Claude Desktop

Add this to your `claude_desktop_config.json`:

```json
"mcpServers": {
  "browser-use": {
    "command": "uv",
    "args": [
        "run",
        "/path/to/browser-use-mcp/src/server.py",
        "--api-key",
        "YOUR_BROWSER_USE_API_KEY"
    ]
  }
}
```

## License

This MCP server is licensed under the MIT License. This means you are free to use, modify, and distribute the software, subject to the terms and conditions of the MIT License. For more details, please see the LICENSE file in the project repository.
