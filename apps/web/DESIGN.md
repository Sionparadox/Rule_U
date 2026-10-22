---
version: 1
name: Rule_U — Game Night
description: 보드게임 테이블 위의 말(meeple) 네 가지 색을 그대로 가져온 모바일 게임풍 규칙 도우미. 누를 수 있을 것처럼 두툼한 버튼, 게임마다 그 게임의 구성물을 그린 타일, 판정을 말의 색으로 보여주는 결과 카드가 중심이다. 형식은 awesome-design-md(VoltAgent)를 따르고, 채도 높은 단색 카드와 큰 라운드는 clay 분석에서, 과정과 정직성 규칙은 taste-skill에서 가져왔다.

colors:
  ground: "#eef3fb" # 테이블 천. 페이지 바닥
  surface: "#fdfeff" # 카드·시트 면
  surface-soft: "#e2e9f6" # 눌린 칸, 세그먼트 바탕
  ink: "#1b2340" # 본문·제목
  muted: "#566079" # 보조 문구 (ground 위 5.6:1)
  edge: "#c9d3e6" # 입력 테두리, 타일 그림자 톤
  blue: "#2f6bff" # 파랑 말 = Rule_U. 주요 동작, 내 질문
  blue-deep: "#1d4fd8" # 파랑 버튼의 두께(아래 그림자)
  red: "#f2545b" # 빨강 말 = 할 수 없어요
  red-deep: "#c9353c"
  green: "#22b573" # 초록 말 = 가능해요
  green-deep: "#168a55"
  green-text: "#127a4b" # 흰 면 위 작은 초록 글자 (4.5:1 이상)
  yellow: "#ffc93c" # 노랑 말 = 조건부, 시작 버튼
  yellow-deep: "#e0a10e"
  on-blue: "#ffffff"

typography:
  display:
    {
      fontFamily: Jua,
      fontSize: 30px,
      lineHeight: 1.15,
      use: "로비 제목, 시트 제목",
    }
  title:
    {
      fontFamily: Jua,
      fontSize: 22px,
      lineHeight: 1.2,
      use: "판정 문구, 대화 제목",
    }
  tile:
    { fontFamily: Jua, fontSize: 18px, lineHeight: 1.25, use: "게임 타일 이름" }
  body:
    {
      fontFamily: Pretendard Variable,
      fontSize: 15px,
      fontWeight: 400,
      lineHeight: 1.65,
    }
  label:
    {
      fontFamily: Pretendard Variable,
      fontSize: 13px,
      fontWeight: 600,
      lineHeight: 1.3,
    }
  button: { fontFamily: Jua, fontSize: 17px, lineHeight: 1 }

rounded: { sm: 10px, md: 16px, lg: 24px, xl: 28px, full: 9999px }

depth:
  press-height: 4px # 버튼·타일의 두께
  button: "0 4px 0 {color}-deep"
  tile: "0 4px 0 {colors.edge}"
  sheet: "0 -8px 32px -12px ink/30%" # 떠 있는 시트만

motion: # 구현: src/lib/motion.ts (motion/react). UI 모션은 300ms 이하, 나갈 때는 더 빠르게.
  press: "CSS. translateY(3px), 두께 1px, 90ms ease-out. 두께 있는 요소에는 motion transform을 걸지 않고 바깥 래퍼에 건다"
  quick: "등장 220ms / 퇴장 120ms, cubic-bezier(0.23,1,0.32,1)"
  settle: "spring 0.32s bounce 0.12. 모드 전환 알약(layoutId), 시트 복귀, 개수 배지"
  playful: "spring 0.45s bounce 0.45. 판정 토큰이 내려앉는 순간에만"
  screens: "대화는 오른쪽에서, 로비는 왼쪽에서 24px 들어온다"
  list: "타일·출처 칩 40–50ms 간격 stagger, 새로 도착한 메시지만 등장 효과"
  sheet: "모바일 바텀 시트는 머리를 아래로 120px 끌거나 빠르게 튕기면 닫힌다"
  dice: "답변을 기다리는 동안 주사위가 구른다"
  reduced: "MotionConfig reducedMotion=user: 이동·확대는 빼고 투명도만 남긴다"
---

## Overview

Rule_U는 게임을 하다 멈춘 사람이 테이블에서 휴대폰을 들고 "이거 돼?"를 묻는 앱이다. 화면은 그 테이블의 말과 구성물로 만든다.

**아이디어 (taste-skill 4단계).** 이 화면에서 **보드게임 말의 네 가지 색**은 **판정의 언어**가 된다. 초록 말은 가능, 빨강 말은 불가, 노랑 말은 조건부, 파랑 말은 Rule_U 자신이다. 다른 규칙 도우미에 대입하면 성립하지 않는다는 점에서 경쟁자 시험을 통과한다.

**Key Characteristics**

- 페이지 바닥은 테이블 천 같은 옅은 하늘색, 그 위에 흰 면의 카드가 놓인다.
- 버튼과 타일은 아래 4px 두께가 있어 누르면 실제로 내려간다. 모바일 게임의 촉감이 여기서 나온다.
- 게임 타일 위쪽 절반은 그 게임의 구성물 그림(육각 타일, 보석 토큰, 단어 카드, 말, 주사위)이다. 장식 아이콘이 아니라 게임 자체를 보여준다.
- 판정은 말 색의 결과 카드로, 아이콘 토큰(✓ ✕ ! ?)과 함께 크게 보인다. 색만으로 구분하지 않는다.

## Colors

말 색 네 개가 시스템의 전부다. 다섯 번째 채도 높은 색은 추가하지 않는다.

- 파랑(`{colors.blue}`)은 Rule_U와 사용자의 행동: 주요 버튼, 내 질문 말풍선, 인용 번호.
- 노랑(`{colors.yellow}`)은 "시작" 한 군데: 게임 시작 버튼, 조건부 판정. 화면당 한 번.
- 초록·빨강은 판정과 출처 확인 상태에만 쓴다. 장식에 쓰지 않는다.
- 밝은 색 면 위 글자는 `{colors.ink}`, 파랑 면 위 글자만 흰색이다 (대비 4.5:1 이상).

## Typography

- 제목·버튼·판정은 **Jua**(둥근 한글 디스플레이, OFL). 게임 UI의 말투를 만든다.
- 본문·라벨은 **Pretendard Variable**. 긴 규칙 설명도 편하게 읽힌다.
- 두 서체 외에는 쓰지 않는다. 숫자는 표 숫자(tnum)로 맞춘다.
- 제목은 두 줄 이하. 기울임과 강조 단어 색칠은 쓰지 않는다.

## Layout

- 모바일 우선, 바깥 여백 16px, 최대 폭 960px(로비)·720px(대화).
- 4px 간격 체계: 4 · 8 · 12 · 16 · 24 · 32 · 48.
- 로비: 제목 → 이어하기 카드 → 검색 → 게임 타일 2열(태블릿 3열, 데스크톱 4열).
- 대화: 상단 바(둥근 뒤로 버튼, 게임 이름, 모드 전환) → 메시지 → 하단 입력.
- 하단 탭 바는 두지 않는다. 목적지가 로비와 대화 둘뿐이라 레퍼런스처럼 탭을 채우면 가짜 목적지가 생긴다.

## Elevation & Depth

| 단계 | 처리                                              | 용도                           |
| ---- | ------------------------------------------------- | ------------------------------ |
| 바닥 | 그림자 없음                                       | 페이지, 상단 바                |
| 면   | `{colors.surface}` + 1.5px `{colors.edge}` 테두리 | 입력, 메시지 카드              |
| 두께 | 아래로 4px 단색 그림자                            | 버튼, 게임 타일, 이어하기 카드 |
| 뜸   | 부드러운 큰 그림자                                | 시트(대화상자)만               |

번지는 글로우와 그라데이션은 쓰지 않는다. 깊이는 단색 두께로만 표현한다.

## Shapes

`{rounded.sm}` 칩·인용 번호 · `{rounded.md}` 버튼·입력 · `{rounded.lg}` 타일·메시지 카드 · `{rounded.xl}` 시트 · `{rounded.full}` 둥근 아이콘 버튼.

## Components

- **`btn-play`** — 노랑 바탕, 잉크 글자, Jua 17px, 높이 52px, 아래 4px `{colors.yellow-deep}`. 게임 시작 전용.
- **`btn-primary`** — 파랑 바탕, 흰 글자, 아래 4px `{colors.blue-deep}`. 검색, 보내기.
- **`btn-soft`** — 흰 면, 잉크 글자, 아래 4px `{colors.edge}`. 보조 동작(게임 변경, 다시 시도).
- **`icon-round`** — 44px 원형 흰 버튼(뒤로, 닫기), 두께 3px.
- **`game-tile`** — 위: 게임 구성물 그림이 있는 말 색 면(높이 112px), 아래: 흰 면에 Jua 이름 + 인원·시간 + 출처 확인 상태. 라운드 `{rounded.lg}`, 두께 4px.
- **`continue-card`** — 최근 대화. 파랑 면, 흰 글자, 구성물 그림 작게, 오른쪽에 노랑 "이어하기" 버튼.
- **`verdict-card`** — 답변 카드 머리. 판정 말 색 면에 아이콘 토큰(흰 원 안 기호)과 Jua 22px 판정 문구. 아래 흰 면에 본문과 출처 칩.
- **`source-chip`** — 파랑 숫자 토큰 + 규칙서 이름 + 쪽수. 누르면 출처 시트.
- **`thinking-card`** — 굴러가는 주사위 + 현재 단계 문구 + 스켈레톤 3줄.
- **`sheet`** — 판본 선택·출처 설명. 위쪽에 게임 그림 띠, 라운드 `{rounded.xl}`.

## Do's and Don'ts

### Do

- 게임 타일에는 그 게임의 구성물을 그린다. 같은 색 타일이 연달아 오지 않게 말 색을 돌린다.
- 누를 수 있는 모든 것에 두께와 눌림을 준다.
- 판정은 색 + 기호 + 문구 세 가지로 동시에 알린다.

### Don't

- 레퍼런스에 있던 별점, 접속자 수, 리더보드, 포인트를 지어내지 않는다 (실제 데이터가 없다).
- 이모지를 아이콘으로 쓰지 않는다. 모든 그림은 SVG로 직접 그린다.
- 그라데이션, 글로우, 유리(블러) 효과를 쓰지 않는다.
- 인라인 색상값을 쓰지 않는다. 모든 색은 토큰으로 참조한다.

## Responsive Behavior

| 폭         | 변화                                              |
| ---------- | ------------------------------------------------- |
| < 640px    | 타일 2열, 시트는 화면 아래에서 올라오는 바텀 시트 |
| 640–1024px | 타일 3열, 시트는 가운데                           |
| > 1024px   | 타일 4열                                          |

터치 대상은 44px 이상. 320px에서도 가로 스크롤이 생기지 않는다.

## Known Gaps

- 실제 게임 110여 개에 개별 그림은 없다. 장르·이름으로 구성물 모티프(육각, 보석, 카드, 말, 주사위)를 고르는 결정적 규칙으로 그린다.
- 다크 모드는 범위 밖이다.
