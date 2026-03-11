#!/usr/bin/env python3
"""
TRPG Scenario Integration Test
===============================
D&D 5e 스타일 미니 시나리오를 시뮬레이션하여 MCP 다이스 서버의 전체 기능을 검증합니다.

시나리오: "잊혀진 던전의 문"
- 전사 캐릭터가 던전 입구에서 문을 발견
- 지각 판정 → 함정 발견 시도
- 함정 해제 or 강행돌파
- 문 뒤 고블린과 전투 (이니셔티브 → 공격 → 데미지)
- 히스토리로 전 과정 확인
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


def result_lines(r) -> str:
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

            errors = []

            # ==============================================================
            header("시나리오: 잊혀진 던전의 문")
            # ==============================================================

            narrate("전사 '아이언하트'가 던전 입구에 도착했다.")
            narrate("낡은 나무 문 앞에 이상한 기운이 감돈다...")

            # ----------------------------------------------------------
            # 1. 지각 판정 (Perception Check, DC 13)
            # ----------------------------------------------------------
            header("PHASE 1: 지각 판정 (Wisdom Check)")
            narrate("함정이 있는지 살펴본다. Wisdom 수정치 +2, DC 13")

            r = await session.call_tool("roll_dice", {
                "notation": "1d20+2",
                "target": 13,
            })
            print(f"\n{result_lines(r)}")
            assert r.isError == False, "roll_dice should succeed"

            text = result_lines(r)
            perception_success = "성공" in text
            if perception_success:
                narrate("함정을 발견했다! 문 손잡이에 독침 장치가 있다.")
            else:
                narrate("특별히 이상한 점은 보이지 않는다...")
            print(f"  → 지각 판정: {'성공' if perception_success else '실패'}")

            # ----------------------------------------------------------
            # 2. 함정 해제 or 강행돌파
            # ----------------------------------------------------------
            header("PHASE 2: 행동 결정")

            if perception_success:
                narrate("손재주(Dexterity) 판정으로 함정을 해제한다. DEX +3, DC 15")
                r = await session.call_tool("roll_dice", {
                    "notation": "1d20+3",
                    "target": 15,
                })
                print(f"\n{result_lines(r)}")
                assert r.isError == False

                if "성공" in result_lines(r):
                    narrate("함정을 무사히 해제했다!")
                else:
                    narrate("해제 실패! 독침에 찔렸다!")
                    narrate("독침 데미지: 1d4")
                    r = await session.call_tool("roll_dice", {"notation": "1d4"})
                    print(f"  Poison damage: {result_lines(r)}")
                    assert r.isError == False
            else:
                narrate("그냥 문을 연다... 독침에 찔렸다!")
                r = await session.call_tool("roll_dice", {"notation": "1d4"})
                print(f"  Poison damage: {result_lines(r)}")
                assert r.isError == False

            # ----------------------------------------------------------
            # 3. 전투 시작: 이니셔티브
            # ----------------------------------------------------------
            header("PHASE 3: 전투 - 이니셔티브")
            narrate("문 뒤에서 고블린 2마리가 튀어나왔다!")
            narrate("이니셔티브 굴림! 아이언하트 DEX +1")

            r_player = await session.call_tool("roll_dice", {"notation": "1d20+1"})
            print(f"\n  아이언하트: {result_lines(r_player)}")
            assert r_player.isError == False

            r_goblin = await session.call_tool("roll_dice", {"notation": "1d20+2"})
            print(f"  고블린들:   {result_lines(r_goblin)}")
            assert r_goblin.isError == False

            # ----------------------------------------------------------
            # 4. 공격 (어드밴티지 포함)
            # ----------------------------------------------------------
            header("PHASE 4: 전투 - 공격 판정")
            narrate("아이언하트가 롱소드로 첫 번째 고블린을 공격한다!")
            narrate("고블린이 넘어져 있어 어드밴티지! STR +4, AC 15")

            r = await session.call_tool("roll_dice", {
                "notation": "1d20+4",
                "advantage": "advantage",
                "target": 15,
            })
            print(f"\n{result_lines(r)}")
            assert r.isError == False

            attack_hit = "성공" in result_lines(r)
            if attack_hit:
                narrate("명중! 롱소드 데미지를 굴린다. 1d8+4")
                r = await session.call_tool("roll_dice", {"notation": "1d8+4"})
                print(f"\n  Damage: {result_lines(r)}")
                assert r.isError == False
                narrate("고블린이 쓰러졌다!")
            else:
                narrate("빗나갔다! 고블린이 재빠르게 피했다.")

            # ----------------------------------------------------------
            # 5. 고블린 반격 (디스어드밴티지)
            # ----------------------------------------------------------
            header("PHASE 5: 전투 - 고블린 반격")
            narrate("두 번째 고블린이 독 묻은 단검으로 공격한다!")
            narrate("하지만 아이언하트의 방패에 눈이 부셔 디스어드밴티지. +4, AC 18")

            r = await session.call_tool("roll_dice", {
                "notation": "1d20+4",
                "advantage": "disadvantage",
                "target": 18,
            })
            print(f"\n{result_lines(r)}")
            assert r.isError == False

            if "성공" in result_lines(r):
                narrate("고블린의 단검이 갑옷 틈을 파고들었다!")
                r = await session.call_tool("roll_dice", {"notation": "1d6+2"})
                print(f"  Dagger damage: {result_lines(r)}")
            else:
                narrate("고블린의 공격이 방패에 튕겨나갔다!")

            # ----------------------------------------------------------
            # 6. 파이어볼! (높은 데미지 다이스)
            # ----------------------------------------------------------
            header("PHASE 6: 마법 공격 - 파이어볼 (보너스)")
            narrate("동료 마법사가 파이어볼을 날린다! 8d6 화염 데미지!")

            r = await session.call_tool("roll_dice", {"notation": "8d6"})
            print(f"\n{result_lines(r)}")
            assert r.isError == False
            narrate("남은 고블린이 불길에 휩싸였다!")

            # ----------------------------------------------------------
            # 7. 보물 발견 - 퍼센타일 다이스
            # ----------------------------------------------------------
            header("PHASE 7: 보물 테이블 (Percentile)")
            narrate("전투 후 보물 상자를 발견했다! 1d100으로 보물 테이블을 참조한다.")

            r = await session.call_tool("roll_dice", {"notation": "1d100"})
            print(f"\n{result_lines(r)}")
            assert r.isError == False

            total_line = [l for l in result_lines(r).split("\n") if l.startswith("Total:")][0]
            loot_roll = int(total_line.split(":")[-1].strip())
            if loot_roll >= 90:
                narrate(f"[{loot_roll}] 대박! 전설적인 마법 검을 발견했다!")
            elif loot_roll >= 50:
                narrate(f"[{loot_roll}] 괜찮은 보물! 금화 50개와 치유 물약을 찾았다.")
            else:
                narrate(f"[{loot_roll}] 소소한 보물... 동전 몇 닢과 낡은 지도.")

            # ----------------------------------------------------------
            # 8. World of Darkness 보너스: 뱀파이어 등장
            # ----------------------------------------------------------
            header("PHASE 8: [보너스] WoD - 뱀파이어의 지배 (Dice Pool)")
            narrate("던전 깊은 곳에서 뱀파이어가 나타났다!")
            narrate("뱀파이어의 지배(Dominate) 다이스 풀: 7d10, 성공 기준 ≥8, 10 폭발")

            r = await session.call_tool("roll_pool", {
                "pool": 7,
                "sides": 10,
                "target": 8,
                "explode": True,
            })
            print(f"\n{result_lines(r)}")
            assert r.isError == False

            narrate("아이언하트의 의지력 저항 풀: 5d10, 성공 기준 ≥8")
            r = await session.call_tool("roll_pool", {
                "pool": 5,
                "sides": 10,
                "target": 8,
            })
            print(f"\n{result_lines(r)}")
            assert r.isError == False

            # ----------------------------------------------------------
            # 9. 에러 핸들링 시나리오
            # ----------------------------------------------------------
            header("PHASE 9: 엣지 케이스 & 에러 핸들링")

            # 잘못된 notation
            print("\n  [Test] 잘못된 notation → isError=True")
            r = await session.call_tool("roll_dice", {"notation": "abc"})
            assert r.isError == True, f"Expected isError=True, got {r.isError}"
            print(f"    ✓ isError=True: {result_lines(r)[:60]}")

            # advantage on non-d20
            print("\n  [Test] 2d6에 advantage → isError=True")
            r = await session.call_tool("roll_dice", {
                "notation": "2d6",
                "advantage": "advantage",
            })
            assert r.isError == True
            print(f"    ✓ isError=True: {result_lines(r)[:60]}")

            # pool 범위 초과
            print("\n  [Test] pool=100 → isError=True")
            r = await session.call_tool("roll_pool", {"pool": 100})
            assert r.isError == True
            print(f"    ✓ isError=True: {result_lines(r)[:60]}")

            # ----------------------------------------------------------
            # 10. 전체 히스토리 확인
            # ----------------------------------------------------------
            header("PHASE 10: 모험 기록 (History)")
            narrate("오늘의 모험 기록을 확인한다...")

            r = await session.call_tool("get_history", {"limit": 20})
            print(f"\n{result_lines(r)}")
            assert r.isError == False

            # 히스토리에 기록이 있는지 확인 (에러는 기록 안 됨)
            text = result_lines(r)
            assert "굴림 기록" in text
            assert "roll_dice" in text
            assert "roll_pool" in text
            print("\n  ✓ 히스토리에 roll_dice, roll_pool 기록 확인")

            # ----------------------------------------------------------
            # 히스토리 클리어
            # ----------------------------------------------------------
            r = await session.call_tool("clear_history", {})
            assert r.isError == False
            assert "삭제" in result_lines(r)
            print(f"  ✓ {result_lines(r)}")

            r = await session.call_tool("get_history", {})
            assert "없습니다" in result_lines(r)
            print(f"  ✓ 클리어 후: {result_lines(r)}")

            # ==============================================================
            header("시나리오 완료!")
            print("""
  ✅ MCP 프로토콜 준수: CallToolResult + isError 정상 동작
  ✅ roll_dice: 기본/modifier/advantage/disadvantage/target/compound/percentile
  ✅ roll_pool: WoD 스타일 성공 카운팅 + 폭발 주사위
  ✅ get_history / clear_history: 기록 관리
  ✅ 에러 핸들링: 잘못된 입력 시 isError=True
  ✅ 전체 TRPG 시나리오 플로우 정상 작동
""")
            print("  🎲 '잊혀진 던전의 문' 시나리오 테스트 완료!")
            print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(run_scenario())
