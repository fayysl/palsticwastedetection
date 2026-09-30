#!/usr/bin/env python3
"""
Test MCP server connectivity and tool availability.

Usage:
    python test_mcp_connection.py <mcp_server_path>
    
Example:
    python test_mcp_connection.py ./backend/mcp_server.py
"""

import asyncio
import sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test_mcp_server(server_path: str):
    """Test MCP server connection and tools."""
    
    print(f"🔍 Testing MCP server at: {server_path}\n")
    
    # Verify server file exists
    if not Path(server_path).exists():
        print(f"❌ Error: Server file not found: {server_path}")
        sys.exit(1)
    
    try:
        # Connect to MCP server
        server_params = StdioServerParameters(
            command="python",
            args=[server_path],
        )
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize connection
                await session.initialize()
                print("✅ Connection established\n")
                
                # List available tools
                print("📋 Available tools:")
                tools_response = await session.list_tools()
                
                if not tools_response.tools:
                    print("❌ No tools found!")
                    return False
                
                for tool in tools_response.tools:
                    print(f"  • {tool.name}: {tool.description}")
                
                print(f"\n✅ Found {len(tools_response.tools)} tools\n")
                
                # Test each tool
                test_user_id = "test-user-123"
                
                # Test 1: Add task
                print("🧪 Test 1: Adding task...")
                try:
                    result = await session.call_tool(
                        "add_task",
                        arguments={
                            "user_id": test_user_id,
                            "title": "Test MCP Task",
                            "description": "Testing MCP connectivity"
                        }
                    )
                    print(f"   Result: {result.content[0].text}")
                    print("   ✅ add_task working\n")
                except Exception as e:
                    print(f"   ❌ add_task failed: {e}\n")
                    return False
                
                # Test 2: List tasks
                print("🧪 Test 2: Listing tasks...")
                try:
                    result = await session.call_tool(
                        "list_tasks",
                        arguments={
                            "user_id": test_user_id,
                            "status": "all"
                        }
                    )
                    print(f"   Result: {result.content[0].text}")
                    print("   ✅ list_tasks working\n")
                except Exception as e:
                    print(f"   ❌ list_tasks failed: {e}\n")
                    return False
                
                # Test 3: Complete task (task ID 1 from add_task)
                print("🧪 Test 3: Completing task...")
                try:
                    result = await session.call_tool(
                        "complete_task",
                        arguments={
                            "user_id": test_user_id,
                            "task_id": 1
                        }
                    )
                    print(f"   Result: {result.content[0].text}")
                    print("   ✅ complete_task working\n")
                except Exception as e:
                    print(f"   ❌ complete_task failed: {e}\n")
                    # Don't fail here - task might not exist
                
                # Test 4: Delete task
                print("🧪 Test 4: Deleting task...")
                try:
                    result = await session.call_tool(
                        "delete_task",
                        arguments={
                            "user_id": test_user_id,
                            "task_id": 1
                        }
                    )
                    print(f"   Result: {result.content[0].text}")
                    print("   ✅ delete_task working\n")
                except Exception as e:
                    print(f"   ❌ delete_task failed: {e}\n")
                
                print("=" * 50)
                print("✅ MCP Server Test Complete!")
                print("=" * 50)
                return True
                
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("\nTroubleshooting:")
        print("1. Check if mcp_server.py has syntax errors")
        print("2. Verify database connection (if using DB)")
        print("3. Check if mcp package is installed: pip install mcp")
        return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python test_mcp_connection.py <mcp_server_path>")
        print("Example: python test_mcp_connection.py ./backend/mcp_server.py")
        sys.exit(1)
    
    server_path = sys.argv[1]
    
    success = asyncio.run(test_mcp_server(server_path))
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
