# Dice MCP Server

A Model Context Protocol (MCP) server for TRPG dice rolling across multiple game systems.

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
| `roll_dice` | Roll dice using standard notation (NdM+X, kh/kl, dF) | `notation`, `advantage`, `bonus_dice`, `target`, `degrees` |
| `roll_pool` | Dice pool with success counting (WoD, Shadowrun) | `pool`, `target`, `explode`, `count_ones` |
| `reroll` | Re-roll last roll with same params | — |
| `get_history` | Retrieve recent roll log | `limit` |
| `clear_history` | Clear roll history | — |

See [CONTEXT.md](CONTEXT.md) for system-specific parameter mappings and invariants.

---

## Parameter Reference

### `roll_dice`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `notation` | string | *required* | Dice expression: `1d20+5`, `4d6kh3`, `4dF+2`, `1d100` |
| `advantage` | bool | `false` | Roll d20 twice, take higher (1d20 only) |
| `disadvantage` | bool | `false` | Roll d20 twice, take lower (1d20 only) |
| `bonus_dice` | int | `0` | CoC bonus dice (0–2, 1d100 only) — extra tens, keep lowest |
| `penalty_dice` | int | `0` | CoC penalty dice (0–2, 1d100 only) — extra tens, keep highest |
| `target` | int | — | DC/AC/skill value for success check |
| `target_mode` | enum | `"at_least"` | `"at_least"` (D&D: ≥) or `"at_most"` (CoC: ≤) |
| `critical` | bool | `false` | Nat 20/1 detection. With `degrees="pf2e"`, shifts degree ±1 step |
| `degrees` | enum | — | `"coc"` / `"pf2e"` / `"pbta"` — enables degree calculation |

### `roll_pool`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pool` | int | *required* | Number of dice (1–50) |
| `sides` | int | `10` | Sides per die |
| `target` | int | `8` | Minimum value for a success (≥) |
| `explode` | bool | `false` | Reroll on max value |
| `double_on` | int | — | Double success at this value or higher (must be ≥ target) |
| `count_ones` | bool | `false` | Enable botch/glitch detection |

### `get_history`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | `10` | Number of recent rolls to retrieve (1–100) |

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
| Savage Worlds | 50% | Exploding works, but no wild die or raise counting |

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
