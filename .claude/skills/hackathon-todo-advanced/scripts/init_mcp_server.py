#!/usr/bin/env python3
"""
Initialize a new MCP server with Official MCP SDK for todo management.

Usage:
    python init_mcp_server.py <output_directory>
    
Example:
    python init_mcp_server.py ./backend/mcp_server
"""

import sys
import os
from pathlib import Path

MCP_SERVER_TEMPLATE = '''"""MCP Server for Todo Task Management."""
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import mcp.types as types
from typing import Any
import asyncio
from sqlmodel import Session, select
from models import Task, engine

# Initialize MCP server
server = Server("todo-mcp-server")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available MCP tools."""
    return [
        types.Tool(
            name="add_task",
            description="Create a new todo task",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "User ID"},
                    "title": {"type": "string", "description": "Task title"},
                    "description": {"type": "string", "description": "Task description (optional)"},
                },
                "required": ["user_id", "title"],
            },
        ),
        types.Tool(
            name="list_tasks",
            description="Retrieve tasks from the list",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "User ID"},
                    "status": {
                        "type": "string",
                        "enum": ["all", "pending", "completed"],
                        "description": "Filter by status",
                    },
                },
                "required": ["user_id"],
            },
        ),
        types.Tool(
            name="complete_task",
            description="Mark a task as complete",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "User ID"},
                    "task_id": {"type": "integer", "description": "Task ID"},
                },
                "required": ["user_id", "task_id"],
            },
        ),
        types.Tool(
            name="delete_task",
            description="Remove a task from the list",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "User ID"},
                    "task_id": {"type": "integer", "description": "Task ID"},
                },
                "required": ["user_id", "task_id"],
            },
        ),
        types.Tool(
            name="update_task",
            description="Modify task title or description",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "User ID"},
                    "task_id": {"type": "integer", "description": "Task ID"},
                    "title": {"type": "string", "description": "New title (optional)"},
                    "description": {"type": "string", "description": "New description (optional)"},
                },
                "required": ["user_id", "task_id"],
            },
        ),
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict[str, Any] | None
) -> list[types.TextContent]:
    """Handle MCP tool calls."""
    
    if not arguments:
        raise ValueError("Missing arguments")
    
    user_id = arguments.get("user_id")
    if not user_id:
        raise ValueError("user_id is required")
    
    # Route to appropriate handler
    if name == "add_task":
        return await add_task_handler(user_id, arguments)
    elif name == "list_tasks":
        return await list_tasks_handler(user_id, arguments)
    elif name == "complete_task":
        return await complete_task_handler(user_id, arguments)
    elif name == "delete_task":
        return await delete_task_handler(user_id, arguments)
    elif name == "update_task":
        return await update_task_handler(user_id, arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")

# Tool Handlers

async def add_task_handler(user_id: str, args: dict) -> list[types.TextContent]:
    """Add a new task."""
    with Session(engine) as session:
        task = Task(
            user_id=user_id,
            title=args["title"],
            description=args.get("description", ""),
            completed=False,
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        
        return [types.TextContent(
            type="text",
            text=f"Task created: ID={task.id}, Title='{task.title}'"
        )]

async def list_tasks_handler(user_id: str, args: dict) -> list[types.TextContent]:
    """List tasks with optional status filter."""
    status = args.get("status", "all")
    
    with Session(engine) as session:
        query = select(Task).where(Task.user_id == user_id)
        
        if status == "pending":
            query = query.where(Task.completed == False)
        elif status == "completed":
            query = query.where(Task.completed == True)
        
        tasks = session.exec(query).all()
        
        if not tasks:
            return [types.TextContent(type="text", text="No tasks found.")]
        
        task_list = "\\n".join([
            f"ID: {task.id} | {'✓' if task.completed else '○'} | {task.title}"
            for task in tasks
        ])
        
        return [types.TextContent(type="text", text=task_list)]

async def complete_task_handler(user_id: str, args: dict) -> list[types.TextContent]:
    """Mark task as complete."""
    task_id = args["task_id"]
    
    with Session(engine) as session:
        task = session.exec(
            select(Task).where(Task.id == task_id, Task.user_id == user_id)
        ).first()
        
        if not task:
            return [types.TextContent(type="text", text=f"Task {task_id} not found.")]
        
        task.completed = True
        session.add(task)
        session.commit()
        
        return [types.TextContent(
            type="text",
            text=f"Task {task_id} marked as complete: '{task.title}'"
        )]

async def delete_task_handler(user_id: str, args: dict) -> list[types.TextContent]:
    """Delete a task."""
    task_id = args["task_id"]
    
    with Session(engine) as session:
        task = session.exec(
            select(Task).where(Task.id == task_id, Task.user_id == user_id)
        ).first()
        
        if not task:
            return [types.TextContent(type="text", text=f"Task {task_id} not found.")]
        
        title = task.title
        session.delete(task)
        session.commit()
        
        return [types.TextContent(
            type="text",
            text=f"Task {task_id} deleted: '{title}'"
        )]

async def update_task_handler(user_id: str, args: dict) -> list[types.TextContent]:
    """Update task title or description."""
    task_id = args["task_id"]
    
    with Session(engine) as session:
        task = session.exec(
            select(Task).where(Task.id == task_id, Task.user_id == user_id)
        ).first()
        
        if not task:
            return [types.TextContent(type="text", text=f"Task {task_id} not found.")]
        
        if "title" in args:
            task.title = args["title"]
        if "description" in args:
            task.description = args["description"]
        
        session.add(task)
        session.commit()
        
        return [types.TextContent(
            type="text",
            text=f"Task {task_id} updated: '{task.title}'"
        )]

async def main():
    """Run the MCP server."""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="todo-mcp-server",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())
'''

def main():
    if len(sys.argv) < 2:
        print("Usage: python init_mcp_server.py <output_directory>")
        sys.exit(1)
    
    output_dir = Path(sys.argv[1])
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create mcp_server.py
    mcp_file = output_dir / "mcp_server.py"
    with open(mcp_file, 'w') as f:
        f.write(MCP_SERVER_TEMPLATE)
    
    print(f"✅ Created MCP server at: {mcp_file}")
    print("\nNext steps:")
    print("1. Update models.py import path if needed")
    print("2. Test with: python test_mcp_connection.py")
    print("3. Integrate with your FastAPI app")

if __name__ == "__main__":
    main()
