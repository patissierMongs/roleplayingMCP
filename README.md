# Dice MCP Server

A Model Context Protocol (MCP) server that provides TRPG dice rolling functionality, containerized with Docker.

## Features

- **Standard dice notation**: Any dice expression — `1d20`, `2d6+3`, `4d6`, `1d100`, `3d20-2d20+2`
- **Keep highest / lowest**: `4d6kh3` (roll 4d6, keep highest 3), `2d20kl1` (keep lowest)
- **Advantage / Disadvantage**: D&D 5e style — roll 1d20 twice, take higher or lower
- **Critical hit / fumble**: Natural 20 / Natural 1 detection (toggleable)
- **Target check**: Automatic success/failure with two modes:
  - `at_least` (D&D): result ≥ target = success
  - `at_most` (CoC/BRP): result ≤ target = success
- **Dice pool / Success counting**: World of Darkness, Shadowrun style — roll N dice, count successes
  - Exploding dice (max value triggers reroll)
  - Double successes on high rolls
  - Botch/Glitch detection (toggleable)
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

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `notation` | string | Yes | — | Dice expression: `1d20+5`, `4d6kh3`, `2d20kl1`, `3d20-2d20` |
| `advantage` | string | No | `"normal"` | `"normal"`, `"advantage"`, `"disadvantage"` (1d20 only) |
| `target` | integer | No | — | DC/AC/skill value for success check |
| `target_mode` | string | No | `"at_least"` | `"at_least"` (D&D: ≥) or `"at_most"` (CoC: ≤) |
| `critical` | boolean | No | `false` | Enable nat 20/1 critical detection on d20 |

**Examples:**

```jsonc
// Basic d20 + modifier
{ "name": "roll_dice", "arguments": { "notation": "1d20+5" } }
// → 1d20: [14]
// → Modifier: +5
// → Total: 19

// Advantage with DC check + critical detection
{ "name": "roll_dice", "arguments": { "notation": "1d20+5", "advantage": "advantage", "target": 15, "critical": true } }
// → Roll (Advantage): 1d20 → [20, 8] → 선택: 20
// → Modifier: +5
// → Total: 25
// → 💥 CRITICAL HIT! (Natural 20)
// → 판정: 성공! (25 ≥ 15)

// D&D ability score generation (4d6 keep highest 3)
{ "name": "roll_dice", "arguments": { "notation": "4d6kh3" } }
// → 4d6kh3: [4, ~~2~~, 5, 6] → kept: [4, 5, 6]
// → Total: 15

// CoC SAN check (at_most mode)
{ "name": "roll_dice", "arguments": { "notation": "1d100", "target": 65, "target_mode": "at_most" } }
// → 1d100: [42]
// → Total: 42
// → 판정: 성공! (42 ≤ 65)

// Fireball damage
{ "name": "roll_dice", "arguments": { "notation": "8d6" } }
// → 8d6: [3, 5, 2, 6, 1, 4, 6, 3]
// → Total: 30

// Negative dice (3d20 minus 2d20)
{ "name": "roll_dice", "arguments": { "notation": "3d20-2d20+2" } }
// → 3d20: [15, 8, 12]
// → -2d20: [6, 11]
// → Total: 35 - 17 +2 = 20
```

### `roll_pool`

Dice pool with success counting.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `pool` | integer | Yes | — | Number of dice (1-50) |
| `sides` | integer | No | `10` | Sides per die |
| `target` | integer | No | `8` | Success threshold |
| `explode` | boolean | No | `false` | Reroll on max value |
| `double_on` | integer | No | — | Double success at this value or higher |
| `count_ones` | boolean | No | `false` | Enable botch/glitch detection |

When `count_ones` is enabled:
- **WoD Botch**: 0 successes + any 1s rolled
- **Shadowrun Glitch**: Half or more dice show 1s
- **Shadowrun Critical Glitch**: Glitch + 0 successes

**Examples:**

```jsonc
// World of Darkness: 6d10, target 8, 10s explode
{ "name": "roll_pool", "arguments": { "pool": 6, "target": 8, "explode": true } }
// → Dice Pool: 6d10 (target ≥ 8, exploding)
// → Rolls: [(10→3), 8, 4, 2, 9, 7]
// → Successes: 3

// WoD with botch detection
{ "name": "roll_pool", "arguments": { "pool": 3, "target": 8, "count_ones": true } }
// → Dice Pool: 3d10 (target ≥ 8, botch/glitch detection ON)
// → Rolls: [1, 4, 2]
// → Successes: 0
// → 1s rolled: 1
// → 🔥 BOTCH! (0 successes with 1s — WoD rule)

// Shadowrun: 8d6, target 5, glitch detection
{ "name": "roll_pool", "arguments": { "pool": 8, "sides": 6, "target": 5, "count_ones": true } }
// → Dice Pool: 8d6 (target ≥ 5, botch/glitch detection ON)
// → Rolls: [1, 1, 1, 1, 5, 3, 2, 6]
// → Successes: 2
// → 1s rolled: 4
// → ⚠️ GLITCH! (half+ dice are 1s — Shadowrun rule)
```

### `get_history`

Retrieve recent roll history.

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `limit` | integer | No | `10` | Number of records to retrieve |

### `clear_history`

Clear all roll history. No parameters.

## Project Structure

```
.
├── server.py           # MCP server — tool registration & handlers
├── dice_parser.py      # Dice notation parser (NdM+K, kh/kl)
├── history.py          # Roll history manager
├── src/                # PyPI package source
│   └── roleplaying_dice_mcp/
│       ├── __init__.py
│       ├── server.py
│       ├── dice_parser.py
│       └── history.py
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
