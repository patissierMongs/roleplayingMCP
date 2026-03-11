#!/usr/bin/env python3
"""
MCP Dice Server - A simple dice rolling server using Model Context Protocol
Provides a tool to roll d20 dice with configurable positive and negative dice counts
Rules:
- Negative dice cannot be used alone
- Positive dice count must be greater than negative dice count
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
            description="Roll d20 dice and return the sum. Default is 1d20. Supports negative dice (must have count > negative_count).",
            inputSchema={
                "type": "object",
                "properties": {
                    "count": {
                        "type": "integer",
                        "description": "Number of positive d20 dice to roll. Default is 1. Must be greater than negative_count.",
                        "default": 1,
                        "minimum": 1
                    },
                    "negative_count": {
                        "type": "integer",
                        "description": "Number of negative d20 dice to roll. Default is 0. Must be less than count. Cannot be used alone.",
                        "default": 0,
                        "minimum": 0
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

    # Get parameters, with defaults
    count = 1
    negative_count = 0

    if arguments:
        if "count" in arguments:
            count = int(arguments["count"])
        if "negative_count" in arguments:
            negative_count = int(arguments["negative_count"])

    # Validate rules
    if count < 1:
        raise ValueError("Positive dice count must be at least 1")

    if negative_count < 0:
        raise ValueError("Negative dice count cannot be negative")

    if negative_count >= count:
        raise ValueError(f"Positive dice count ({count}) must be greater than negative dice count ({negative_count})")

    # Roll positive dice
    positive_rolls = []
    for _ in range(count):
        roll = random.randint(1, 20)
        positive_rolls.append(roll)

    # Roll negative dice
    negative_rolls = []
    for _ in range(negative_count):
        roll = random.randint(1, 20)
        negative_rolls.append(roll)

    # Calculate sum
    positive_sum = sum(positive_rolls)
    negative_sum = sum(negative_rolls)
    total = positive_sum - negative_sum

    # Format the result
    if negative_count == 0:
        # Only positive dice
        if count == 1:
            result_text = f"Rolled 1d20: {positive_rolls[0]}\nSum: {total}"
        else:
            rolls_str = ", ".join(str(r) for r in positive_rolls)
            result_text = f"Rolled {count}d20: [{rolls_str}]\nSum: {total}"
    else:
        # Both positive and negative dice
        positive_str = ", ".join(str(r) for r in positive_rolls)
        negative_str = ", ".join(str(r) for r in negative_rolls)
        result_text = f"Rolled {count}d20: [{positive_str}]\n"
        result_text += f"Rolled -{negative_count}d20: [{negative_str}]\n"
        result_text += f"Sum: {positive_sum} - {negative_sum} = {total}"

    return [
        types.TextContent(
            type="text",
            text=result_text
        )
    ]


async def _run():
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


def main():
    """Entry point for the CLI command"""
    asyncio.run(_run())
