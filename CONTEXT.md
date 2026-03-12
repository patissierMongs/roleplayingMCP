---
name: roleplaying-dice-mcp
version: 4.0.0
---

# Roleplaying Dice MCP — Agent Context

## Tool Selection Guide

- `roll_dice`: Standard notation rolls. Use for any "roll XdY" request.
- `roll_pool`: Dice pool systems (WoD, Shadowrun). Use when user mentions "pool", "successes", "exploding dice", or "botch/glitch".
- `reroll`: Repeats last roll with identical params. Use for "reroll", "inspiration", "lucky".
- `get_history` / `clear_history`: Session roll log management.

## System Mapping (which params for which TRPG)

- **D&D 5e**: `notation="1d20+N"`, `advantage=true`, `critical=true`, `target=DC`, `target_mode="at_least"`
- **CoC 7e**: `notation="1d100"`, `bonus_dice=N`, `target=skill`, `target_mode="at_most"`, `degrees="coc"`
- **PF2e**: `notation="1d20+N"`, `target=DC`, `critical=true`, `degrees="pf2e"`
- **PbtA**: `notation="2d6+N"`, `degrees="pbta"`
- **FATE**: `notation="4dF+N"`
- **WoD**: `roll_pool`, `pool=N`, `target=8`, `explode=true`, `count_ones=true`
- **Shadowrun**: `roll_pool`, `pool=N`, `sides=6`, `target=5`, `count_ones=true`

## Invariants

- `advantage` and `disadvantage` are mutually exclusive and only apply to 1d20.
- `bonus_dice` and `penalty_dice` are mutually exclusive and only apply to 1d100.
- `advantage`/`disadvantage` and `bonus_dice`/`penalty_dice` cannot be combined.
- `degrees` requires `target` to be set (except `pbta` which uses fixed thresholds).
- `critical` with `degrees="pf2e"` shifts the degree ±1 step on nat 20/1.
- `count_ones` in `roll_pool`: detects WoD Botch (0 successes + any 1s) and Shadowrun Glitch (half+ dice are 1s).
- `reroll` fails if no previous roll exists in the session.
- `double_on` must be >= `target` in `roll_pool`.

## Response Format

- All tool responses return plain text with individual die results, totals, and applicable flags (success/failure, degree, critical status).
- Degree labels use English terms: Critical, Extreme Success, Hard Success, Regular Success, Fumble (CoC); Critical Success/Failure, Success, Failure (PF2e); Strong Hit, Weak Hit, Miss (PbtA).
- Botch/glitch results include emoji markers for visibility.
