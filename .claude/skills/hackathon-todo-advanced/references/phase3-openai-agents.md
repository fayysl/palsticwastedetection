# Phase 3: OpenAI Agents SDK Integration

## Overview

The OpenAI Agents SDK bridges your FastAPI chat endpoint and MCP server. It:
- Manages conversation context
- Routes tool calls to your MCP server
- Handles multi-turn conversations
- Maintains agent state and reasoning

## Installation

```bash
cd backend
uv add openai-agents-sdk
# or
pip install openai-agents-sdk --break-system-packages
```

## Architecture

```
User Message → FastAPI → Agent SDK → OpenAI API
                  ↓           ↓
                  ↓       Tool Call?
                  ↓           ↓
                  ↓        MCP Server
                  ↓           ↓
                  ↓      Execute Tool
                  ↓           ↓
             Database ← Store Result
```

## Agent Configuration

### Basic Agent Setup

```python
# agents/todo_agent.py
from openai import OpenAI
from typing import Any
import json
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class TodoAgent:
    """AI agent for managing todo tasks via natural language."""
    
    def __init__(self, mcp_server_path: str, openai_api_key: str):
        self.client = OpenAI(api_key=openai_api_key)
        self.mcp_server_path = mcp_server_path
        self.model = "gpt-4o"  # or gpt-4-turbo
        
    async def run(
        self,
        user_id: str,
        messages: list[dict[str, str]]
    ) -> tuple[str, list[dict]]:
        """
        Run agent with MCP tools.
        
        Args:
            user_id: Current user's ID
            messages: Conversation history + new message
            
        Returns:
            (response_text, tool_calls_metadata)
        """
        
        # Connect to MCP server
        server_params = StdioServerParameters(
            command="python",
            args=[self.mcp_server_path],
        )
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as mcp_session:
                await mcp_session.initialize()
                
                # Get MCP tools
                tools_response = await mcp_session.list_tools()
                mcp_tools = tools_response.tools
                
                # Convert MCP tools to OpenAI function format
                openai_tools = self._convert_tools(mcp_tools)
                
                # Build system prompt
                system_message = self._build_system_prompt(user_id)
                full_messages = [system_message] + messages
                
                # Call OpenAI with tools
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=full_messages,
                    tools=openai_tools,
                    tool_choice="auto",
                )
                
                # Process response
                assistant_message = response.choices[0].message
                tool_calls_metadata = []
                
                # Handle tool calls
                if assistant_message.tool_calls:
                    # Agent wants to use tools
                    tool_results = []
                    
                    for tool_call in assistant_message.tool_calls:
                        tool_name = tool_call.function.name
                        tool_args = json.loads(tool_call.function.arguments)
                        
                        # Inject user_id into tool arguments
                        tool_args["user_id"] = user_id
                        
                        # Call MCP tool
                        mcp_result = await mcp_session.call_tool(
                            tool_name,
                            arguments=tool_args
                        )
                        
                        # Extract text result
                        result_text = mcp_result.content[0].text if mcp_result.content else ""
                        
                        # Store for metadata
                        tool_calls_metadata.append({
                            "tool": tool_name,
                            "arguments": tool_args,
                            "result": result_text,
                        })
                        
                        # Add to conversation for final response
                        tool_results.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": result_text,
                        })
                    
                    # Get final response with tool results
                    full_messages.append({
                        "role": "assistant",
                        "content": assistant_message.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                }
                            }
                            for tc in assistant_message.tool_calls
                        ],
                    })
                    full_messages.extend(tool_results)
                    
                    final_response = self.client.chat.completions.create(
                        model=self.model,
                        messages=full_messages,
                    )
                    
                    response_text = final_response.choices[0].message.content
                else:
                    # No tool calls, direct response
                    response_text = assistant_message.content
                
                return response_text, tool_calls_metadata
    
    def _build_system_prompt(self, user_id: str) -> dict[str, str]:
        """Build system prompt for the agent."""
        return {
            "role": "system",
            "content": f"""You are a helpful todo assistant for user {user_id}.

Your job is to help users manage their todo list through natural language conversation.

CRITICAL RULES:
1. ALWAYS use MCP tools for task operations. Never make up or simulate task data.
2. When the user wants to add a task, call add_task with the title they provide.
3. When the user wants to see tasks, call list_tasks with appropriate status filter.
4. When the user wants to complete a task, call complete_task with the task ID.
5. When the user wants to delete a task, call delete_task with the task ID.
6. When the user wants to update a task, call update_task with new details.

CONVERSATION STYLE:
- Be friendly and concise
- Confirm actions clearly ("I've added 'Buy groceries' to your list")
- Ask for clarification when task details are ambiguous
- If user references "the meeting task" but there are multiple, ask which one

EXAMPLES:
User: "Add buy groceries to my list"
→ Call add_task(user_id="{user_id}", title="Buy groceries")
→ Respond: "I've added 'Buy groceries' to your todo list."

User: "What do I need to do?"
→ Call list_tasks(user_id="{user_id}", status="pending")
→ Respond with formatted task list

User: "Mark task 5 as done"
→ Call complete_task(user_id="{user_id}", task_id=5)
→ Respond: "Great! I've marked task 5 as complete."
"""
        }
    
    def _convert_tools(self, mcp_tools: list) -> list[dict]:
        """Convert MCP tools to OpenAI function calling format."""
        openai_tools = []
        
        for tool in mcp_tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema,
                },
            })
        
        return openai_tools
```

## Integration with Chat Endpoint

Update your chat route to use the agent:

```python
# routes/chat.py
from agents.todo_agent import TodoAgent
import os

# Initialize agent (do this once, outside the route)
agent = TodoAgent(
    mcp_server_path="./mcp_server.py",
    openai_api_key=os.getenv("OPENAI_API_KEY")
)

async def run_agent_with_mcp(
    user_id: str,
    messages: list[dict[str, str]]
) -> tuple[str, list[dict]]:
    """Helper function called from chat endpoint."""
    return await agent.run(user_id, messages)
```

## Advanced Agent Patterns

### Multi-Tool Workflows

The agent can chain multiple tool calls in one turn:

```
User: "Add 'Call mom' and 'Pay bills' to my list, then show me everything"

Agent will:
1. Call add_task(title="Call mom")
2. Call add_task(title="Pay bills")  
3. Call list_tasks(status="all")
4. Respond with summary
```

### Conversational Context

Agent maintains context across turns:

```
User: "Add buy milk"
Agent: "Added 'Buy milk' to your list."

User: "Actually, make that 2 gallons"
Agent: [Calls list_tasks to find the milk task]
      [Calls update_task to change title]
      "Updated to 'Buy 2 gallons of milk'."
```

### Error Handling

```python
# In TodoAgent.run()
try:
    mcp_result = await mcp_session.call_tool(tool_name, arguments=tool_args)
except Exception as e:
    # Log error but don't crash
    result_text = f"Error: {str(e)}"
    tool_calls_metadata.append({
        "tool": tool_name,
        "arguments": tool_args,
        "result": result_text,
        "error": True,
    })
```

## Natural Language Understanding

### Task Extraction

The agent should intelligently extract task details:

```
"Remind me to call the dentist next week"
→ add_task(title="Call dentist", description="Next week")

"I need to finish the report by Friday"
→ add_task(title="Finish report", description="Due Friday")
```

### Task References

Handle vague references:

```
User: "Delete the grocery task"
Agent: [Calls list_tasks to find tasks with "grocery" in title]
       [If multiple, asks which one]
       [If one, calls delete_task with that ID]
```

## Testing the Agent

### Unit Test

```python
# tests/test_agent.py
import pytest
from agents.todo_agent import TodoAgent

@pytest.mark.asyncio
async def test_agent_add_task():
    agent = TodoAgent(
        mcp_server_path="./mcp_server.py",
        openai_api_key="sk-test-key"
    )
    
    messages = [
        {"role": "user", "content": "Add buy groceries to my list"}
    ]
    
    response, tools = await agent.run(
        user_id="test-user",
        messages=messages
    )
    
    assert "groceries" in response.lower()
    assert len(tools) == 1
    assert tools[0]["tool"] == "add_task"
```

### Integration Test

```python
# Test full conversation flow
@pytest.mark.asyncio
async def test_full_conversation():
    # Add task
    response1, _ = await agent.run("test-user", [
        {"role": "user", "content": "Add call mom"}
    ])
    assert "added" in response1.lower()
    
    # List tasks
    response2, _ = await agent.run("test-user", [
        {"role": "user", "content": "Add call mom"},
        {"role": "assistant", "content": response1},
        {"role": "user", "content": "What's on my list?"}
    ])
    assert "call mom" in response2.lower()
```

## Performance Optimization

### Token Management

Limit conversation history to prevent token overflow:

```python
def truncate_history(messages: list[dict], max_tokens: int = 4000):
    """Keep only recent messages to stay under token limit."""
    # Keep system message + last N turns
    if len(messages) > 20:
        return [messages[0]] + messages[-19:]
    return messages
```

### Caching

Cache MCP tool list to avoid repeated fetches:

```python
from functools import lru_cache

@lru_cache(maxsize=1)
async def get_mcp_tools():
    """Cache MCP tools list."""
    # ... fetch tools once
```

## Common Issues & Solutions

### Issue: Agent not using tools correctly
**Solution**: Improve system prompt with more explicit examples

### Issue: Tool arguments missing user_id
**Solution**: Always inject user_id before calling MCP tools

### Issue: Agent timeout
**Solution**: Set reasonable timeout for OpenAI API calls:
```python
response = self.client.chat.completions.create(
    ...,
    timeout=30.0
)
```

### Issue: Conversation context too long
**Solution**: Implement message truncation (see above)

## Next Steps

1. Test agent with various natural language queries
2. Refine system prompt based on agent behavior
3. Add conversation history truncation for long conversations
4. Integrate with ChatKit frontend (see phase3-chatkit-setup.md)
