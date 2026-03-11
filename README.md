# Dice MCP Server

A Model Context Protocol (MCP) server that provides TRPG dice rolling functionality, containerized with Docker.

## Features

- **Standard dice notation**: Any dice expression — `1d20`, `2d6+3`, `4d6`, `1d100`, `3d20-2d20+2`
- **Advantage / Disadvantage**: D&D 5e style — roll 1d20 twice, take higher or lower
- **Dice pool / Success counting**: World of Darkness, Shadowrun style — roll N dice, count successes
  - Exploding dice (max value triggers reroll)
  - Double successes on high rolls
- **Target (DC/AC) check**: Automatic success/failure判定
- **Roll history**: Track and review recent rolls per session
- **MCP-compliant error handling**: Errors returned as `TextContent`, never crashes

## Quick Start (uvx)

No installation needed. Just configure Claude Desktop:

**`claude_desktop_config.json`**:
```json
{
  "mcpServers": {
    "dice": {
      "command": "uvx",
      "args": ["roleplaying-dice-mcp"]
    }
  }
}
```

That's it! Claude Desktop will automatically download and run the server.

> Config file location:
> - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
> - Windows: `%APPDATA%\Claude\claude_desktop_config.json`

## Alternative: Install with pip

```bash
pip install roleplaying-dice-mcp
```

Then configure Claude Desktop:
```json
{
  "mcpServers": {
    "dice": {
      "command": "roleplaying-dice-mcp"
    }
  }
}
```

## Alternative: Docker

```bash
docker build -t dice-mcp-server .
docker run -i dice-mcp-server
```

```json
{
  "mcpServers": {
    "dice": {
      "command": "docker",
      "args": ["run", "-i", "dice-mcp-server"]
    }
  }
}
```

## Tools

### `roll_dice`

Roll dice using standard TRPG notation.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `notation` | string | Yes | Dice expression: `1d20+5`, `2d6+3`, `3d20-2d20` |
| `advantage` | string | No | `"normal"`, `"advantage"`, `"disadvantage"` (1d20 only) |
| `target` | integer | No | DC/AC — adds success/failure check |

**Examples:**

```jsonc
// Basic d20 + modifier
{ "name": "roll_dice", "arguments": { "notation": "1d20+5" } }
// → 1d20: [14]
// → Modifier: +5
// → Total: 19

// Advantage with DC check
{ "name": "roll_dice", "arguments": { "notation": "1d20+5", "advantage": "advantage", "target": 15 } }
// → Roll (Advantage): 1d20 → [14, 8] → 선택: 14
// → Modifier: +5
// → Total: 19
// → 판정: 성공! (19 ≥ 15)

// Fireball damage
{ "name": "roll_dice", "arguments": { "notation": "8d6" } }
// → 8d6: [3, 5, 2, 6, 1, 4, 6, 3]
// → Total: 30

// Negative dice (3d20 minus 2d20)
{ "name": "roll_dice", "arguments": { "notation": "3d20-2d20+2" } }
// → 3d20: [15, 8, 12]
// → -2d20: [6, 11]
// → Modifier: +2
// → Total: 35 - 17 +2 = 20
```

### `roll_pool`

Dice pool with success counting.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `pool` | integer | Yes | Number of dice (1-50) |
| `sides` | integer | No | Sides per die (default: 10) |
| `target` | integer | No | Success threshold (default: 8) |
| `explode` | boolean | No | Reroll on max value (default: false) |
| `double_on` | integer | No | Double success at this value or higher |

**Example:**

```jsonc
// World of Darkness: 6d10, target 8, 10s explode
{ "name": "roll_pool", "arguments": { "pool": 6, "target": 8, "explode": true } }
// → Dice Pool: 6d10 (target ≥ 8, exploding)
// → Rolls: [(10→3), 8, 4, 2, 9, 7]
// → Successes: 3
```

### `get_history`

Retrieve recent roll history.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `limit` | integer | No | Number of records (default: 10) |

### `clear_history`

Clear all roll history. No parameters.

## Project Structure

```
.
├── server.py           # MCP server — tool registration & handlers
├── dice_parser.py      # Dice notation parser (NdM+K)
├── history.py          # Roll history manager
├── src/                # PyPI package source
│   └── roleplaying_dice_mcp/
│       ├── __init__.py
│       └── server.py
├── tests/
│   └── test_trpg_scenario.py
├── pyproject.toml      # Package configuration
├── requirements.txt    # Python dependencies
├── Dockerfile          # Container definition
├── docker-compose.yml  # Compose configuration
└── README.md
```

## Local Development

```bash
# Direct
pip install -r requirements.txt
python server.py

# Editable install
pip install -e .
roleplaying-dice-mcp
```

## License

MIT
