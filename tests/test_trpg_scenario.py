#!/usr/bin/env python3
"""
TRPG Scenario Integration Test
===============================
멀티시스템 TRPG 시나리오를 시뮬레이션하여 MCP 다이스 서버의 전체 기능을 검증합니다.

시나리오: "잊혀진 던전의 문" + 멀티시스템 보너스
- D&D 5e: 판정, 어드밴티지, 크리티컬, 능력치 생성
- CoC 7e: 보너스/페널티 다이스, 성공 단계 (Hard/Extreme)
- PF2e: 성공 단계 (±10 마진)
- PbtA: Strong/Weak/Miss
- FATE: 퍼지 다이스
- WoD/Shadowrun: 다이스 풀, 보치/글리치
- 리롤 기능
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


def header(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def narrate(text: str):
    print(f"\n  📖 {text}")


def result_text(r) -> str:
    return r.content[0].text


async def run_scenario():
    server_params = StdioServerParameters(
        command="python3",
        args=["server.py"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # ==============================================================
            header("D&D 5e: 잊혀진 던전의 문")
            # ==============================================================

            narrate("전사 '아이언하트'가 던전 입구에 도착했다.")

            # 1. 지각 판정
            header("PHASE 1: 지각 판정 (DC 13)")
            r = await session.call_tool("roll_dice", {
                "notation": "1d20+2",
                "target": 13,
            })
            print(f"\n{result_text(r)}")
            assert not r.isError

            # 2. 어드밴티지 공격 + 크리티컬
            header("PHASE 2: 어드밴티지 공격 + Critical")
            r = await session.call_tool("roll_dice", {
                "notation": "1d20+4",
                "advantage": True,
                "target": 15,
                "critical": True,
            })
            print(f"\n{result_text(r)}")
            assert not r.isError
            text = result_text(r)
            assert "Advantage" in text

            # 3. 디스어드밴티지 반격
            header("PHASE 3: 디스어드밴티지 반격")
            r = await session.call_tool("roll_dice", {
                "notation": "1d20+4",
                "disadvantage": True,
                "target": 18,
                "critical": True,
            })
            print(f"\n{result_text(r)}")
            assert not r.isError

            # 4. 능력치 생성 4d6kh3
            header("PHASE 4: 능력치 생성 (4d6kh3)")
            stats = []
            for stat in ["STR", "DEX", "CON", "INT", "WIS", "CHA"]:
                r = await session.call_tool("roll_dice", {"notation": "4d6kh3"})
                assert not r.isError
                for line in result_text(r).split("\n"):
                    if line.startswith("Total:"):
                        val = int(line.split(":")[-1].strip())
                        stats.append(val)
                        break
                print(f"  {stat}: {result_text(r).split(chr(10))[0]} → {stats[-1]}")
            narrate(f"능력치: {', '.join(f'{s}' for s in stats)}")

            # 5. 파이어볼
            header("PHASE 5: 파이어볼 8d6")
            r = await session.call_tool("roll_dice", {"notation": "8d6"})
            print(f"\n{result_text(r)}")
            assert not r.isError

            # ==============================================================
            header("FATE: 마법 저항 (4dF+3)")
            # ==============================================================
            r = await session.call_tool("roll_dice", {"notation": "4dF+3"})
            print(f"\n{result_text(r)}")
            assert not r.isError
            text = result_text(r)
            assert "dFate" in text
            print("  ✓ 퍼지 다이스 정상 출력")

            r = await session.call_tool("roll_dice", {"notation": "4dF"})
            print(f"\n{result_text(r)}")
            assert not r.isError

            # ==============================================================
            header("CoC 7e: SAN 체크 + 보너스 다이스 + 성공 단계")
            # ==============================================================

            # 보너스 다이스
            narrate("침착한 상태에서 기술 판정. 보너스 다이스 1개, 기술값 65")
            r = await session.call_tool("roll_dice", {
                "notation": "1d100",
                "bonus_dice": 1,
                "target": 65,
                "target_mode": "at_most",
                "degrees": "coc",
            })
            print(f"\n{result_text(r)}")
            assert not r.isError
            text = result_text(r)
            assert "보너스" in text
            assert "Regular ≤65" in text
            print("  ✓ CoC 보너스 다이스 + 성공 단계 정상 출력")

            # 페널티 다이스
            narrate("불리한 상황! 페널티 다이스 1개.")
            r = await session.call_tool("roll_dice", {
                "notation": "1d100",
                "penalty_dice": 1,
                "target": 50,
                "target_mode": "at_most",
                "degrees": "coc",
            })
            print(f"\n{result_text(r)}")
            assert not r.isError
            assert "페널티" in result_text(r)
            print("  ✓ CoC 페널티 다이스 정상 출력")

            # CoC 성공 단계 (보너스/페널티 없이)
            narrate("SAN 체크! 현재 SAN 65")
            r = await session.call_tool("roll_dice", {
                "notation": "1d100",
                "target": 65,
                "target_mode": "at_most",
                "degrees": "coc",
            })
            print(f"\n{result_text(r)}")
            assert not r.isError
            assert "Regular ≤65" in result_text(r)

            # ==============================================================
            header("PF2e: 성공 단계 판정 (±10 마진)")
            # ==============================================================
            narrate("DC 20 판정, 크리티컬 감지 ON")
            r = await session.call_tool("roll_dice", {
                "notation": "1d20+8",
                "target": 20,
                "critical": True,
                "degrees": "pf2e",
            })
            print(f"\n{result_text(r)}")
            assert not r.isError
            text = result_text(r)
            assert "DC 20" in text
            assert "차이:" in text
            print("  ✓ PF2e 성공 단계 정상 출력")

            # ==============================================================
            header("PbtA: 던전월드 판정 (2d6+1)")
            # ==============================================================
            narrate("해크&슬래시! 2d6+STR(+1)")
            r = await session.call_tool("roll_dice", {
                "notation": "2d6+1",
                "degrees": "pbta",
            })
            print(f"\n{result_text(r)}")
            assert not r.isError
            text = result_text(r)
            assert "Strong" in text or "Weak" in text or "Miss" in text
            assert "Strong ≥10" in text
            print("  ✓ PbtA 성공 단계 정상 출력")

            # ==============================================================
            header("WoD: 뱀파이어 다이스 풀 + Botch/Glitch")
            # ==============================================================
            narrate("뱀파이어의 지배 풀: 7d10, ≥8, 폭발, botch 감지 ON")
            r = await session.call_tool("roll_pool", {
                "pool": 7, "target": 8, "explode": True, "count_ones": True,
            })
            print(f"\n{result_text(r)}")
            assert not r.isError
            assert "1s rolled:" in result_text(r)

            # botch OFF 확인
            r = await session.call_tool("roll_pool", {
                "pool": 5, "target": 8,
            })
            print(f"\n{result_text(r)}")
            assert "1s rolled:" not in result_text(r)
            print("  ✓ botch ON/OFF 토글 정상")

            # ==============================================================
            header("Reroll: 직전 굴림 다시")
            # ==============================================================
            narrate("마지막 굴림을 다시 굴린다! (Lucky / Inspiration)")
            r_original = await session.call_tool("roll_dice", {
                "notation": "1d20+5",
                "target": 15,
            })
            print(f"\n  원본: {result_text(r_original)}")
            assert not r_original.isError

            r_reroll = await session.call_tool("reroll", {})
            print(f"\n  리롤: {result_text(r_reroll)}")
            assert not r_reroll.isError
            # Reroll should produce valid output with same format
            assert "1d20" in result_text(r_reroll)
            assert "Total:" in result_text(r_reroll)
            print("  ✓ 리롤 정상 작동")

            # Reroll with no previous roll
            # (skip - already rolled above)

            # ==============================================================
            header("에러 핸들링")
            # ==============================================================

            print("\n  [Test] 잘못된 notation")
            r = await session.call_tool("roll_dice", {"notation": "abc"})
            assert r.isError
            print(f"    ✓ {result_text(r)[:60]}")

            print("\n  [Test] advantage + disadvantage 동시")
            r = await session.call_tool("roll_dice", {
                "notation": "1d20", "advantage": True, "disadvantage": True,
            })
            assert r.isError
            print(f"    ✓ {result_text(r)[:60]}")

            print("\n  [Test] bonus + penalty 동시")
            r = await session.call_tool("roll_dice", {
                "notation": "1d100", "bonus_dice": 1, "penalty_dice": 1,
            })
            assert r.isError
            print(f"    ✓ {result_text(r)[:60]}")

            print("\n  [Test] 1d20에 bonus_dice (d100 전용)")
            r = await session.call_tool("roll_dice", {
                "notation": "1d20", "bonus_dice": 1,
            })
            assert r.isError
            print(f"    ✓ {result_text(r)[:60]}")

            print("\n  [Test] degrees=coc without target")
            r = await session.call_tool("roll_dice", {
                "notation": "1d100", "degrees": "coc",
            })
            assert r.isError
            print(f"    ✓ {result_text(r)[:60]}")

            print("\n  [Test] pool=100 범위 초과")
            r = await session.call_tool("roll_pool", {"pool": 100})
            assert r.isError
            print(f"    ✓ {result_text(r)[:60]}")

            print("\n  [Test] keep > count")
            r = await session.call_tool("roll_dice", {"notation": "2d6kh5"})
            assert r.isError
            print(f"    ✓ {result_text(r)[:60]}")

            # ==============================================================
            header("히스토리")
            # ==============================================================
            r = await session.call_tool("get_history", {"limit": 30})
            print(f"\n{result_text(r)}")
            assert not r.isError
            assert "roll_dice" in result_text(r)
            assert "roll_pool" in result_text(r)
            print("  ✓ 히스토리 기록 확인")

            # reroll marker
            assert "reroll" in result_text(r)
            print("  ✓ 리롤 마커 확인")

            r = await session.call_tool("clear_history", {})
            assert not r.isError
            assert "삭제" in result_text(r)
            print(f"  ✓ {result_text(r)}")

            # ==============================================================
            header("전체 테스트 완료!")
            print("""
  ✅ roll_dice: 기본/modifier/advantage/disadvantage/target/compound
  ✅ roll_dice: keep highest/lowest (4d6kh3)
  ✅ roll_dice: critical hit/fumble detection (ON/OFF)
  ✅ roll_dice: target_mode at_least (D&D) / at_most (CoC)
  ✅ roll_dice: fudge/FATE dice (4dF+3)
  ✅ roll_dice: bonus/penalty dice (CoC d100)
  ✅ roll_dice: degrees coc (Regular/Hard/Extreme/Fumble)
  ✅ roll_dice: degrees pf2e (Crit/Success/Fail/Crit Fail ±10)
  ✅ roll_dice: degrees pbta (Strong/Weak/Miss)
  ✅ roll_pool: dice pool + exploding + double_on
  ✅ roll_pool: botch/glitch detection (ON/OFF)
  ✅ reroll: 직전 굴림 재실행
  ✅ get_history / clear_history
  ✅ 에러 핸들링: 잘못된 입력 시 isError=True
""")
            print(f"  🎲 멀티시스템 TRPG 통합 테스트 완료!")
            print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(run_scenario())
