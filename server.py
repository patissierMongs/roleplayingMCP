#!/usr/bin/env python3
"""
MCP Dice Server - A simple dice rolling server using Model Context Protocol
Provides a tool to roll d20 dice with configurable count (including negative values)
"""

import asyncio
import random
from typing import Any
from mcp.server.models import InitializationOptions
import mcp.types as types
from mcp.server import NotificationOptions, Server
import mcp.server.stdio


# Create server instance
server = Server("dice-server")


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools - in this case, just the dice roller"""
    return [
        types.Tool(
            name="roll_dice",
            description="Roll d20 dice and return the sum. Default is 1d20. Supports negative dice counts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "count": {
                        "type": "integer",
                        "description": "Number of d20 dice to roll (can be negative). Default is 1.",
                        "default": 1
                    }
                },
                "required": []
            }
        )
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict[str, Any] | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool calls - execute the dice roll"""

    if name != "roll_dice":
        raise ValueError(f"Unknown tool: {name}")

    # Get count parameter, default to 1
    count = 1
    if arguments and "count" in arguments:
        count = int(arguments["count"])

    # Roll the dice
    rolls = []
    for _ in range(abs(count)):
        roll = random.randint(1, 20)
        rolls.append(roll)

    # Calculate sum with sign based on count
    if count >= 0:
        total = sum(rolls)
        sign = ""
    else:
        total = -sum(rolls)
        sign = "-"

    # Format the result
    if len(rolls) == 0:
        result_text = "No dice rolled (count = 0)\nSum: 0"
    elif len(rolls) == 1:
        result_text = f"Rolled 1d20: {rolls[0]}\nSum: {total}"
    else:
        rolls_str = ", ".join(str(r) for r in rolls)
        result_text = f"Rolled {abs(count)}d20: [{rolls_str}]\nSum: {sign}{sum(rolls)} = {total}"

    return [
        types.TextContent(
            type="text",
            text=result_text
        )
    ]


async def main():
    """Run the MCP server using stdio transport"""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="dice-server",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                )
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
