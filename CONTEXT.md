---
name: roleplaying-dice-mcp
version: 5.0.0
---

# Roleplaying Dice MCP — Agent Context

This server is a dice *mechanics* engine: it rolls fairly and returns raw JSON.
You (the agent) own all game-system rules — judge success, criticals, degrees,
botches, and glitches yourself from the returned values, and narrate them in
the user's language.

## Tool Selection Guide

- `roll_dice`: Any "roll XdY" request. Notation covers modifiers, compound
  groups, keep highest/lowest (`kh`/`kl`), and Fudge dice (`dF`). CoC-style
  bonus/penalty tens dice via the `bonus_dice`/`penalty_dice` params.
- `roll_pool`: Pool systems that count successes (WoD, Shadowrun). Use when
  the user mentions "pool", "successes", or "exploding dice".
- `reroll`: Repeats the last roll with identical params. Use for "reroll",
  "inspiration", "lucky".
- `get_history` / `clear_history`: Session roll log — an audit trail players
  can check.

## System Idioms (rules are yours to apply)

- **D&D 5e**: normal `1d20+N`; advantage `2d20kh1+N`; disadvantage
  `2d20kl1+N`; stats `4d6kh3`. Judge vs DC/AC; the natural die is `kept[0]`
  for nat 20/1 criticals.
- **CoC 7e**: `1d100` with `bonus_dice`/`penalty_dice`. Judge ≤ skill;
  Hard ≤ skill/2, Extreme ≤ skill/5, 01 critical, fumble 96–100
  (100 only if skill ≥ 50).
- **PF2e**: `1d20+N`. Judge by margin vs DC (±10 = critical), shift one
  degree step on nat 20/1.
- **PbtA**: `2d6+N`. 10+ strong hit, 7–9 weak hit, ≤6 miss.
- **FATE**: `4dF+N`.
- **WoD**: `roll_pool` with `pool=N`, `sides=10`, `target=8`, `explode=true`.
  Botch = 0 `successes` with `ones` > 0.
- **Shadowrun**: `roll_pool` with `pool=N`, `sides=6`, `target=5`.
  Glitch = `ones` ≥ half of `dice_rolled`.

## Invariants

- `bonus_dice` and `penalty_dice` are mutually exclusive and require the
  notation to be exactly a single `1d100` group.
- `double_on` must be >= `target` in `roll_pool`.
- `reroll` fails if no roll has been made this session.
- History holds the last 100 rolls in memory (per server process).

## Response Format

- Successful rolls return one JSON object as text content.
- `roll_dice`: `{notation, groups: [{dice, negative, rolls, kept, dropped,
  subtotal}], modifier, total}` where `total = sum(subtotals) + modifier`.
  With bonus/penalty dice: `{notation, bonus_dice, penalty_dice, units_die,
  tens_dice, candidates, result, modifier, total}`.
- `roll_pool`: `{pool, sides, target, explode, double_on, dice (per-die
  chains), successes, ones, dice_rolled}`.
- Fudge dice roll values are `-1` / `0` / `1`.
- `reroll` responses carry `"reroll": true`.
- `get_history` returns a JSON array (most recent first); `clear_history`
  returns `{"cleared": N}`.
- Errors return `isError=true` with a plain-text message.
