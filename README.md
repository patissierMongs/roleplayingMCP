# Dice MCP Server

A Model Context Protocol (MCP) server that provides TRPG dice rolling functionality for multiple game systems.

## Features

- **Standard dice notation**: `1d20`, `2d6+3`, `4d6`, `1d100`, `3d20-2d20+2`
- **Fudge/FATE dice**: `4dF`, `4dF+3` — each die rolls -1, 0, or +1
- **Keep highest / lowest**: `4d6kh3`, `2d20kl1`
- **Advantage / Disadvantage**: D&D 5e style (bool ON/OFF)
- **Bonus / Penalty dice**: CoC style — extra tens dice on d100 (int 0-2)
- **Critical hit / fumble**: Natural 20/1 detection (bool ON/OFF)
- **Target check**: Two modes — `at_least` (D&D: ≥) / `at_most` (CoC: ≤)
- **Success degrees**: System-specific degree calculation
  - `coc`: Regular / Hard / Extreme / Critical / Fumble
  - `pf2e`: Crit Success / Success / Failure / Crit Failure (±10 margin, nat 20/1 shift)
  - `pbta`: Strong Hit / Weak Hit / Miss (fixed thresholds)
- **Dice pool**: WoD, Shadowrun — success counting, exploding, double successes
  - Botch/Glitch detection (bool ON/OFF)
- **Reroll**: Re-roll last roll with same parameters (Inspiration, Lucky, etc.)
- **Roll history**: Track and review recent rolls per session

## Quick Start (uvx)

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

## Alternative: pip / Docker

```bash
pip install roleplaying-dice-mcp
roleplaying-dice-mcp
```

```bash
docker build -t dice-mcp-server . && docker run -i dice-mcp-server
```

## Tools

### `roll_dice`

Roll dice using standard TRPG notation.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `notation` | string | *required* | Dice expression: `1d20+5`, `4d6kh3`, `4dF+2`, `1d100` |
| `advantage` | bool | `false` | Roll d20 twice, take higher (1d20 only) |
| `disadvantage` | bool | `false` | Roll d20 twice, take lower (1d20 only) |
| `bonus_dice` | int | `0` | CoC bonus dice (0-2, 1d100 only) — extra tens, keep lowest |
| `penalty_dice` | int | `0` | CoC penalty dice (0-2, 1d100 only) — extra tens, keep highest |
| `target` | int | — | DC/AC/skill value for success check |
| `target_mode` | string | `"at_least"` | `"at_least"` (D&D: ≥) or `"at_most"` (CoC: ≤) |
| `critical` | bool | `false` | Nat 20/1 detection. With `degrees="pf2e"`, shifts degree ±1 step |
| `degrees` | string | — | `"coc"` / `"pf2e"` / `"pbta"` — enables degree calculation |

**Examples:**

```jsonc
// D&D 5e: advantage + critical + DC
{ "notation": "1d20+5", "advantage": true, "target": 15, "critical": true }

// D&D ability scores
{ "notation": "4d6kh3" }

// FATE
{ "notation": "4dF+3" }

// CoC: bonus die + degrees
{ "notation": "1d100", "bonus_dice": 1, "target": 65, "target_mode": "at_most", "degrees": "coc" }
// → 1d100 (보너스 ×1): [43, 73] → 43
// → 판정: 하드 성공! (43 ≤ 32)  ← wait, depends on roll

// PF2e: degrees with nat 20/1 shift
{ "notation": "1d20+8", "target": 20, "critical": true, "degrees": "pf2e" }

// PbtA: fixed thresholds
{ "notation": "2d6+1", "degrees": "pbta" }
```

### `roll_pool`

Dice pool with success counting.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pool` | int | *required* | Number of dice (1-50) |
| `sides` | int | `10` | Sides per die |
| `target` | int | `8` | Success threshold (≥) |
| `explode` | bool | `false` | Reroll on max value |
| `double_on` | int | — | Double success at this value or higher |
| `count_ones` | bool | `false` | Botch/Glitch detection |

When `count_ones` is enabled:
- **WoD Botch**: 0 successes + any 1s
- **Shadowrun Glitch**: Half+ dice are 1s
- **Shadowrun Critical Glitch**: Glitch + 0 successes

```jsonc
// WoD: 7d10, exploding, botch detection
{ "pool": 7, "target": 8, "explode": true, "count_ones": true }

// Shadowrun: 8d6, target 5, glitch detection
{ "pool": 8, "sides": 6, "target": 5, "count_ones": true }
```

### `reroll`

Re-roll the last `roll_dice` or `roll_pool` with identical parameters. No arguments.

### `get_history` / `clear_history`

| Tool | Parameter | Description |
|------|-----------|-------------|
| `get_history` | `limit` (default 10) | Retrieve recent roll records |
| `clear_history` | — | Clear all history |

## System Coverage

| System | Coverage | Key Features Used |
|--------|----------|-------------------|
| D&D 5e | 95% | notation, advantage, critical, target, 4d6kh3 |
| CoC 7e | 85% | d100, bonus/penalty dice, degrees=coc, at_most |
| PF2e | 85% | d20+mod, degrees=pf2e, critical (nat 20/1 shift) |
| PbtA | 90% | 2d6+mod, degrees=pbta |
| FATE | 95% | 4dF+mod |
| WoD | 90% | roll_pool, explode, count_ones (botch) |
| Shadowrun | 85% | roll_pool (d6), count_ones (glitch) |
| Savage Worlds | 50% | exploding works, but no wild die or raise counting |

## Project Structure

```
├── server.py              # MCP server — tools & handlers
├── dice_parser.py         # Notation parser (NdM, NdF, kh/kl)
├── history.py             # Roll history manager
├── src/roleplaying_dice_mcp/  # PyPI package
├── tests/test_trpg_scenario.py
├── pyproject.toml
├── Dockerfile
└── README.md
```

## License

MIT
