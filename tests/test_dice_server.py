#!/usr/bin/env python3
"""
Dice Server Integration Test
============================
MCP 클라이언트로 서버를 구동해 전체 기능을 검증합니다.

서버는 메커니즘(굴림)만 담당하고 룰 판정은 에이전트 몫이므로,
여기서는 JSON 출력의 구조와 수치 일관성을 검증합니다.
- 노테이션 굴림: 단일/복합/수정치/음수 그룹/kh·kl/퍼지
- CoC 보너스/페널티 십의 자리 주사위
- 다이스 풀: 성공 카운트, 폭발, double_on, 1 개수
- reroll / 히스토리 / 에러 핸들링
"""

import asyncio
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


def header(title: str):
    print(f"\n{'=' * 60}\n  {title}\n{'=' * 60}")


def payload(r) -> dict | list:
    return json.loads(r.content[0].text)


def check_dice_total(p: dict):
    """total == 그룹 subtotal 합 + modifier, subtotal == kept 합(부호 반영)."""
    assert p["total"] == sum(g["subtotal"] for g in p["groups"]) + p["modifier"], p
    for g in p["groups"]:
        expected = -sum(g["kept"]) if g["negative"] else sum(g["kept"])
        assert g["subtotal"] == expected, g
        assert sorted(g["kept"] + g["dropped"]) == sorted(g["rolls"]), g


async def run_tests():
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "roleplaying_dice_mcp"],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONPATH": os.path.join(REPO_ROOT, "src")},
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            header("툴 목록")
            tools = await session.list_tools()
            names = {t.name for t in tools.tools}
            assert names == {
                "roll_dice", "roll_pool", "reroll", "get_history", "clear_history",
            }, names
            print(f"  ✓ 5개 툴 노출: {sorted(names)}")

            header("reroll: 첫 굴림 전에는 에러")
            r = await session.call_tool("reroll", {})
            assert r.isError
            print(f"  ✓ {r.content[0].text[:60]}")

            header("기본 굴림: 1d20+2")
            r = await session.call_tool("roll_dice", {"notation": "1d20+2"})
            assert not r.isError
            p = payload(r)
            check_dice_total(p)
            assert len(p["groups"][0]["rolls"]) == 1
            assert 1 <= p["groups"][0]["rolls"][0] <= 20
            assert p["modifier"] == 2
            print(f"  ✓ {p['notation']} → total {p['total']}")

            header("어드밴티지 관용구: 2d20kh1+4")
            r = await session.call_tool("roll_dice", {"notation": "2d20kh1+4"})
            assert not r.isError
            p = payload(r)
            check_dice_total(p)
            g = p["groups"][0]
            assert len(g["rolls"]) == 2 and len(g["kept"]) == 1
            assert g["kept"][0] == max(g["rolls"])
            print(f"  ✓ rolls {g['rolls']} → kept {g['kept']} (natural die)")

            header("디스어드밴티지 관용구: 2d20kl1+4")
            r = await session.call_tool("roll_dice", {"notation": "2d20kl1+4"})
            assert not r.isError
            g = payload(r)["groups"][0]
            assert g["kept"][0] == min(g["rolls"])
            print(f"  ✓ rolls {g['rolls']} → kept {g['kept']}")

            header("능력치 생성: 4d6kh3 ×6")
            for stat in ["STR", "DEX", "CON", "INT", "WIS", "CHA"]:
                r = await session.call_tool("roll_dice", {"notation": "4d6kh3"})
                assert not r.isError
                p = payload(r)
                check_dice_total(p)
                g = p["groups"][0]
                assert len(g["kept"]) == 3 and len(g["dropped"]) == 1
                assert min(g["kept"]) >= max(g["dropped"] or [0])
                print(f"  {stat}: {g['rolls']} → {p['total']}")

            header("복합 노테이션: 2d6+1d4+3")
            r = await session.call_tool("roll_dice", {"notation": "2d6+1d4+3"})
            assert not r.isError
            p = payload(r)
            check_dice_total(p)
            assert len(p["groups"]) == 2 and p["modifier"] == 3
            print(f"  ✓ total {p['total']}")

            header("음수 그룹: 3d20-2d20")
            r = await session.call_tool("roll_dice", {"notation": "3d20-2d20"})
            assert not r.isError
            p = payload(r)
            check_dice_total(p)
            assert p["groups"][1]["negative"] is True
            assert p["groups"][1]["subtotal"] <= 0
            print(f"  ✓ subtotals {[g['subtotal'] for g in p['groups']]} → {p['total']}")

            header("퍼지 다이스: 4dF+3")
            r = await session.call_tool("roll_dice", {"notation": "4dF+3"})
            assert not r.isError
            p = payload(r)
            check_dice_total(p)
            g = p["groups"][0]
            assert g["dice"] == "4dF"
            assert all(v in (-1, 0, 1) for v in g["rolls"])
            print(f"  ✓ rolls {g['rolls']} → total {p['total']}")

            header("CoC 보너스 다이스: 1d100 + bonus×1")
            r = await session.call_tool("roll_dice", {
                "notation": "1d100", "bonus_dice": 1,
            })
            assert not r.isError
            p = payload(r)
            assert len(p["candidates"]) == 2
            assert p["result"] == min(p["candidates"])
            assert p["total"] == p["result"] + p["modifier"]
            for t, c in zip(p["tens_dice"], p["candidates"]):
                expected = t * 10 + p["units_die"]
                assert c == (100 if expected == 0 else expected)
            print(f"  ✓ candidates {p['candidates']} → {p['result']} (keep lowest)")

            header("CoC 페널티 다이스: 1d100 + penalty×2")
            r = await session.call_tool("roll_dice", {
                "notation": "1d100", "penalty_dice": 2,
            })
            assert not r.isError
            p = payload(r)
            assert len(p["candidates"]) == 3
            assert p["result"] == max(p["candidates"])
            print(f"  ✓ candidates {p['candidates']} → {p['result']} (keep highest)")

            header("다이스 풀: 8d10 ≥8, 폭발")
            r = await session.call_tool("roll_pool", {
                "pool": 8, "target": 8, "explode": True,
            })
            assert not r.isError
            p = payload(r)
            assert len(p["dice"]) == 8
            flat = [v for chain in p["dice"] for v in chain]
            assert p["dice_rolled"] == len(flat)
            assert p["successes"] == sum(1 for v in flat if v >= 8)
            assert p["ones"] == sum(1 for v in flat if v == 1)
            for chain in p["dice"]:
                for v in chain[:-1]:
                    assert v == 10  # 폭발 체인은 마지막 값 이전이 모두 최대값
            print(f"  ✓ dice {p['dice']} → {p['successes']} successes, {p['ones']} ones")

            header("다이스 풀: double_on=10")
            r = await session.call_tool("roll_pool", {
                "pool": 10, "sides": 10, "target": 8, "double_on": 10,
            })
            assert not r.isError
            p = payload(r)
            flat = [v for chain in p["dice"] for v in chain]
            expected = sum(2 if v >= 10 else 1 for v in flat if v >= 8)
            assert p["successes"] == expected
            print(f"  ✓ successes {p['successes']} (double on 10)")

            header("Shadowrun 스타일: 6d6 ≥5 (글리치 판정은 에이전트 몫)")
            r = await session.call_tool("roll_pool", {
                "pool": 6, "sides": 6, "target": 5,
            })
            assert not r.isError
            p = payload(r)
            assert "ones" in p and "dice_rolled" in p
            text = r.content[0].text
            assert "GLITCH" not in text and "BOTCH" not in text
            print(f"  ✓ 원시 데이터만 반환: ones={p['ones']}, dice_rolled={p['dice_rolled']}")

            header("룰 파라미터 제거 확인: 알 수 없는 인자는 무시")
            r = await session.call_tool("roll_dice", {
                "notation": "1d20+5", "target": 15, "critical": True,
            })
            assert not r.isError
            text = r.content[0].text
            assert "Success" not in text and "CRITICAL" not in text
            print("  ✓ 서버는 판정하지 않음 (target/critical 무시)")

            header("Reroll")
            r = await session.call_tool("roll_dice", {"notation": "1d20+5"})
            assert not r.isError
            r2 = await session.call_tool("reroll", {})
            assert not r2.isError
            p2 = payload(r2)
            assert p2["reroll"] is True
            assert p2["notation"] == "1d20+5"
            check_dice_total(p2)
            print(f"  ✓ reroll → total {p2['total']}")

            header("에러 핸들링")
            cases = [
                ("잘못된 notation", "roll_dice", {"notation": "abc"}),
                ("bonus+penalty 동시", "roll_dice",
                 {"notation": "1d100", "bonus_dice": 1, "penalty_dice": 1}),
                ("1d20에 bonus_dice", "roll_dice",
                 {"notation": "1d20", "bonus_dice": 1}),
                ("keep > count", "roll_dice", {"notation": "2d6kh5"}),
                ("pool 범위 초과", "roll_pool", {"pool": 100}),
                ("double_on < target", "roll_pool",
                 {"pool": 5, "target": 8, "double_on": 6}),
            ]
            for label, tool, tool_args in cases:
                r = await session.call_tool(tool, tool_args)
                assert r.isError, label
                print(f"  ✓ {label}: {r.content[0].text[:55]}")

            header("히스토리")
            r = await session.call_tool("get_history", {"limit": 50})
            assert not r.isError
            records = payload(r)
            assert isinstance(records, list) and len(records) > 0
            tools_used = {rec["tool"] for rec in records}
            assert tools_used == {"roll_dice", "roll_pool"}, tools_used
            assert any("(reroll)" in rec["input"] for rec in records)
            print(f"  ✓ {len(records)}건 기록, reroll 마커 확인")

            r = await session.call_tool("clear_history", {})
            assert not r.isError
            assert payload(r)["cleared"] == len(records)
            r = await session.call_tool("get_history", {})
            assert payload(r) == []
            print("  ✓ clear_history 정상")

            header("전체 테스트 통과! 🎲")


if __name__ == "__main__":
    asyncio.run(run_tests())
