# Dice MCP Server

A Model Context Protocol (MCP) server that gives AI agents fair dice.

**The server rolls; the agent rules.** An LLM can narrate any TRPG and already
knows the rules — what it cannot do is produce fair random numbers. This server
provides exactly that missing piece: honest rolls, raw structured results, and
a verifiable roll history. It deliberately contains no game-system rules —
success/failure, criticals, degrees of success, botches and glitches are
judgments the agent makes from the returned values. That keeps the server
small and finished, while supporting effectively every dice-based system.

## Quick Start

### uvx (recommended)

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

> Config: macOS `~/Library/Application Support/Claude/claude_desktop_config.json` / Windows `%APPDATA%\Claude\claude_desktop_config.json`

### pip / Docker

```bash
pip install roleplaying-dice-mcp
roleplaying-dice-mcp
```

```bash
docker build -t dice-mcp-server . && docker run -i dice-mcp-server
```

## Tools

| Tool | Purpose | Key Params |
|------|---------|------------|
| `roll_dice` | Standard notation rolls (NdM+X, kh/kl, dF, compound) | `notation`, `bonus_dice`, `penalty_dice` |
| `roll_pool` | Dice pool with success and 1s counting | `pool`, `sides`, `target`, `explode`, `double_on` |
| `reroll` | Re-roll last roll with same params | — |
| `get_history` | Retrieve recent roll log (JSON) | `limit` |
| `clear_history` | Clear roll history | — |

See [CONTEXT.md](CONTEXT.md) for agent-facing usage notes and per-system idioms.

## Parameter Reference

### `roll_dice`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `notation` | string | *required* | Dice expression: `1d20+5`, `4d6kh3`, `2d20kh1+4`, `4dF+2`, `2d6+1d4+1`, `1d100` |
| `bonus_dice` | int | `0` | CoC-style bonus tens dice (0–2, `1d100` only): extra tens dice share one units die, lowest result kept |
| `penalty_dice` | int | `0` | CoC-style penalty tens dice (0–2, `1d100` only): extra tens dice share one units die, highest result kept |

Bonus/penalty dice are kept as parameters because they change *how the dice
are physically rolled* (a shared units die with multiple tens dice) — they
cannot be expressed in plain notation.

### `roll_pool`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pool` | int | *required* | Number of dice (1–50) |
| `sides` | int | `10` | Sides per die |
| `target` | int | `8` | Minimum value that counts as one success (≥) |
| `explode` | bool | `false` | Reroll on max value; rerolls extend the die's chain |
| `double_on` | int | — | Values at or above this count as two successes (must be ≥ `target`) |

### `get_history`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | `10` | Number of recent rolls to retrieve (1–100) |

## Output Format

All successful rolls return a single JSON object so the agent can compute and
narrate in the session's language.

`roll_dice` (`"4d6kh3+2"`):

```json
{
  "notation": "4d6kh3+2",
  "groups": [
    {"dice": "4d6kh3", "negative": false, "rolls": [5, 3, 6, 1],
     "kept": [6, 5, 3], "dropped": [1], "subtotal": 14}
  ],
  "modifier": 2,
  "total": 16
}
```

`roll_dice` with `bonus_dice` (`"1d100"`):

```json
{
  "notation": "1d100", "bonus_dice": 1, "penalty_dice": 0,
  "units_die": 3, "tens_dice": [4, 7], "candidates": [43, 73],
  "result": 43, "modifier": 0, "total": 43
}
```

`roll_pool` (exploding chains appear per die):

```json
{
  "pool": 6, "sides": 10, "target": 8, "explode": true, "double_on": null,
  "dice": [[10, 3], [8], [4], [1], [9], [7]],
  "successes": 3, "ones": 1, "dice_rolled": 7
}
```

Fudge dice roll values are `-1` / `0` / `1`. Errors return `isError: true`
with a plain-text message.

## Using Game Systems

The agent maps system rules onto these primitives — no server change needed:

| System | Roll | Agent judges |
|--------|------|--------------|
| D&D 5e | `1d20+MOD`; advantage `2d20kh1+MOD`; stats `4d6kh3` | vs DC/AC, nat 20/1 criticals |
| CoC 7e | `1d100` (+ `bonus_dice`/`penalty_dice`) | ≤ skill; Hard ≤ ½, Extreme ≤ ⅕, 01 crit, 96–100 fumble |
| PF2e | `1d20+MOD` | degrees by ±10 margin, nat 20/1 step shift |
| PbtA | `2d6+MOD` | 10+ strong hit, 7–9 weak hit, ≤6 miss |
| FATE | `4dF+MOD` | vs opposition ladder |
| WoD | `roll_pool` sides 10, target 8, explode | botch from `successes` + `ones` |
| Shadowrun | `roll_pool` sides 6, target 5 | glitch from `ones` vs `dice_rolled` |

Any other dice-based system works the same way.

## Project Structure

```
├── src/roleplaying_dice_mcp/
│   ├── server.py          # MCP server — tools & handlers
│   ├── dice_parser.py     # Notation parser (NdM, NdF, kh/kl)
│   └── history.py         # Roll history manager
├── tests/test_dice_server.py
├── pyproject.toml
├── Dockerfile
└── README.md
```

## License

MIT
