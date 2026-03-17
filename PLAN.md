# Architecture Fix Plan v5.1

## 문제 1: Strategy Pattern 과잉 — RollStrategy/PoolStrategy 제거

**진단**: RollStrategy 3개 구현체는 런타임에 교체되지 않음.
roller.py의 if/elif가 선택하므로 분기를 다른 파일로 옮긴 것에 불과.
PoolStrategy는 구현체가 1개 — 추상화할 이유 없음.

**처방**:
- `RollStrategy` ABC + 3개 구현체 삭제
- `PoolStrategy` ABC + 1개 구현체 삭제
- DiceRoller의 private 메서드로 흡수
- `DegreeStrategy` + `DEGREE_REGISTRY`만 유지 (진짜 Strategy)
- `strategies/` → `strategies/degrees.py`만 남김

## 문제 2: `result.total = total  # type: ignore` — 모델 결함

**진단**: RollResult에 없는 필드를 동적으로 붙이고 type: ignore.

**처방**:
- RollResult에 `total: int`, `natural_value: int | None` 정식 필드 추가
- type: ignore 전부 제거

## 문제 3: Config 미연결 필드

**진단**: `max_dice_count`, `max_dice_sides`가 config에 선언됐지만 사용처 없음.

**처방**: 삭제. dice_parser의 한계값은 파서 자체의 불변 규칙. YAGNI.

## 문제 4: HistoryBackend Protocol 타입 누수 + 외부 mutation

**진단**: `get()` 반환이 `list`. roller.py가 `records[0].input_desc` 직접 mutate.

**처방**:
- `get()` 반환을 `list[RollRecord]`로 명시
- reroll 마커: roller에서 history.add() 시 input_desc에 직접 포함 (외부 mutation 제거)
- RollRecord를 models.py로 이동 (공유 모델)
