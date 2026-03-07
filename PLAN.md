# TRPG MCP 주사위 서버 개선 계획

## 현재 상태
- d20 하나만 굴릴 수 있는 단일 tool (`roll_dice`)
- negative dice라는 비표준 개념 사용
- `raise ValueError`로 에러 처리 (MCP 비친화적)
- 상태 관리 없음

---

## Phase 1: 다이스 노테이션 파서 + 다양한 주사위 지원

**목표**: `NdM+K` 표준 다이스 노테이션을 파싱하여 모든 TRPG 주사위를 지원

### 변경사항
- `dice_parser.py` 신규 생성 — 다이스 노테이션 파서
  - 지원 포맷: `1d20`, `2d6+3`, `4d6-1`, `1d20+5`, `1d100`, `3d8+2d6+5`
  - 복합 수식 지원: `+`, `-` 연산자로 여러 주사위 그룹과 상수 조합
  - 정규식 기반 파싱: `(\d+)d(\d+)` 패턴 + modifier
- `roll_dice` tool 스키마 변경:
  - `notation` (string): 다이스 노테이션 문자열 (예: `"2d6+3"`)
  - 기존 `count`/`negative_count` 파라미터 제거

### 지원되는 주사위
- d4, d6, d8, d10, d12, d20, d100 (사실상 dN 어떤 값이든 가능)

---

## Phase 2: 어드밴티지/디스어드밴티지

**목표**: D&D 5e 핵심 메카닉인 advantage/disadvantage 지원

### 변경사항
- `roll_dice` tool에 `advantage` 파라미터 추가:
  - `"normal"` (기본값): 일반 굴림
  - `"advantage"`: 2번 굴려서 높은 값 선택
  - `"disadvantage"`: 2번 굴려서 낮은 값 선택
- 어드밴티지/디스어드밴티지는 단일 주사위 굴림(예: `1d20+5`)에만 적용
- 결과에 두 굴림 모두 표시하고 선택된 값 강조

### 출력 예시
```
Roll with Advantage: 1d20+5
Rolls: [14, 8] → 선택: 14
Result: 14 + 5 = 19
```

---

## Phase 3: 성공 카운팅 (Success Counting)

**목표**: World of Darkness, Shadowrun 등에서 사용하는 성공 판정 시스템 지원

### 변경사항
- 새로운 tool `roll_pool` 추가:
  - `pool` (integer): 주사위 풀 크기 (몇 개를 굴릴지)
  - `sides` (integer, 기본 10): 주사위 면 수
  - `target` (integer, 기본 8): 성공 기준값 (이상이면 성공)
  - `explode` (boolean, 기본 false): 최대값이 나오면 추가 굴림 (폭발 주사위)
  - `double_on` (integer, optional): 이 값 이상이면 성공 2개로 카운트
- 결과: 각 주사위 값, 성공 수, 대성공/대실패 여부

### 출력 예시
```
Dice Pool: 6d10 (target: 8, exploding)
Rolls: [10→3, 8, 4, 2, 9, 7]
Successes: 3 (10→8, 9 성공 / 10 폭발→3 실패)
```

---

## Phase 4: 에러 처리 개선

**목표**: `raise ValueError` 대신 MCP 친화적 에러 응답 반환

### 변경사항
- 모든 에러를 `types.TextContent`로 반환 (is_error=True 플래그 활용)
- 에러 메시지를 사용자 친화적으로 변경
- 잘못된 노테이션에 대한 구체적 피드백 제공
  - 예: `"2d0"` → `"주사위 면 수는 1 이상이어야 합니다"`
  - 예: `"abc"` → `"올바른 다이스 노테이션이 아닙니다. 예: 2d6+3"`

### 적용 범위
- `roll_dice`: 잘못된 notation, 범위 초과 등
- `roll_pool`: 잘못된 pool 크기, target 범위 등
- 알 수 없는 tool 이름 호출

---

## Phase 5: 상태 관리 (굴림 히스토리)

**목표**: 세션 중 굴림 기록을 유지하고 조회할 수 있게 함

### 변경사항
- 새로운 tool `get_history` 추가:
  - `limit` (integer, 기본 10): 최근 N개의 굴림 조회
- 새로운 tool `clear_history` 추가
- 서버 메모리에 굴림 히스토리 저장 (리스트)
  - 각 기록: timestamp, tool명, 입력, 결과, 총합
  - 최대 100개까지 보관 (FIFO)
- `roll_dice`, `roll_pool` 호출 시 자동으로 히스토리에 추가

### 출력 예시 (get_history)
```
=== 최근 굴림 기록 ===
[3] 2d6+3 → [4, 2] + 3 = 9
[2] 1d20+5 (advantage) → [18, 7] → 18 + 5 = 23
[1] 6d10 pool (target:8) → 3 successes
```

---

## Phase 6: 마무리

### 변경사항
- `docker-compose.yml`에서 deprecated `version` 필드 제거
- `Dockerfile`에서 여러 .py 파일 복사하도록 수정 (`COPY *.py .` 또는 개별 COPY)
- README.md 업데이트 (새로운 tool들과 사용 예시 반영)

---

## 최종 Tool 목록

| Tool | 용도 | 핵심 파라미터 |
|------|------|---------------|
| `roll_dice` | 표준 다이스 굴림 | `notation`, `advantage` |
| `roll_pool` | 성공 카운팅 다이스 풀 | `pool`, `sides`, `target`, `explode` |
| `get_history` | 굴림 기록 조회 | `limit` |
| `clear_history` | 기록 초기화 | - |

## 파일 구조 (예상)

```
.
├── server.py           # MCP 서버 메인 (tool 등록 + 핸들러)
├── dice_parser.py      # 다이스 노테이션 파서
├── dice_pool.py        # 성공 카운팅 로직
├── history.py          # 굴림 히스토리 관리
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```
