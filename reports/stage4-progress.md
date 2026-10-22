# 4단계 화면·API 통합

- 날짜: 2026-10-22
- 대상: Windows 로컬 Next.js/FastAPI 애플리케이션. 공개 배포와 5단계 검색 고도화는 제외.
- 상태: 4단계 구현·최종 통합 검증 완료.

## 구현

- Next.js App Router·TypeScript를 유지하고 Tailwind CSS 4, Zustand, Motion, ESLint 9, Prettier를 추가했다. Pretendard는 npm 패키지에서 로컬 제공한다. ESLint는 Next.js 플러그인의 peer dependency 범위에 맞춰 9로 고정했다.
- 사용자 선택인 보드게임 테이블 디자인을 적용했다. 밝은 바탕·딥그린·주황, SVG 주사위 토큰, 모바일 단일 열/태블릿 2열/데스크톱 3열로 구성했다. 근거는 작은 화면에서 접을 수 있고 키보드 포커스·모션 감소 설정을 지원한다.
- `anthropics/skills`의 `frontend-design`을 사용자 스킬 폴더에 설치하고 디자인 검토에 적용했다. 스킬 자동 탐색은 다음 턴부터 적용된다.
- 게임 이름·별칭·인원·최대 시간·장르 검색과 페이지 이동, 자연어 메타데이터 검색, 판본·호환 확장 선택, 규칙 질문/상황 판정, 인용 패널·원문 다운로드를 연결했다.
- Zustand에는 게임/판본/정렬된 확장 조합별 대화 ID와 초안·미확인 전송을 보관한다. 대화 본문은 서버에서 다시 읽으며 쿠키 소유권 검사 후 복원한다. 이전 기반 화면의 저장된 대화 ID도 읽어 새 저장 형식으로 전환한다.
- 새로고침 후 서버의 진행 요청을 다시 조회한다. 전송 결과 불명확 시 같은 `client_request_id`, 확정 실패 후 재시도 시 새 ID를 사용한다. 접수 확인 전에는 새 질문 입력을 막아 다른 초안을 조용히 잃지 않도록 했다.
- 실제 서버 단계인 접수·근거 검색·답변 생성·완료/실패를 표시한다. 수행하지 않는 문서 수집 단계를 가짜 진행 상태로 표시하지 않는다.

## API 계약

| 변경 | 내용 |
|---|---|
| `GET /api/v1/games` | 이름/별칭, players, max_minutes, category, page, page_size. 시간 상한은 SQLite의 최대 시간 기준이며 0(미등록)은 제외 |
| `POST /api/v1/games/search` | query와 동일한 구조화 조건, 메타데이터 의미 순위 + SQLite 최종 재검증 |
| `GET /api/v1/game-categories` | 등록된 장르 목록 |
| 게임 목록/상세 | min_minutes, max_minutes, categories, source_review 추가. 확장은 edition_ids로 호환 판본 제공 |
| 대화 조회 | active_request_id, latest_request_id, latest_client_request_id, 메시지 mode 및 타입이 지정된 citations 추가 |
| 근거 조회 | `SourceOut` 계약과 original_available 추가, 기존 인용 스냅샷 유지 |
| `GET /api/v1/documents/{id}/original` | 해당 문서를 인용한 대화의 세션만 접근. originals 내부 경로 검증, attachment·nosniff·private/no-store 응답 |

스키마는 추가 필드 중심이며 DB 마이그레이션은 필요 없다. OpenAPI와 생성된 TypeScript 타입을 함께 갱신했다. 기존 202 응답·중복 요청 방지·동일 출처 프록시를 유지했다.

자연어의 명확한 숫자 표현(`4명`, `30분 이내`)과 등록 장르를 구조화하며 명시적 필터가 우선한다. 나머지 표현은 의미 검색에 사용한다. 모든 자연어 표현의 논리 조건 파싱을 보장하지 않으므로 정확한 제한은 필터로 지정한다. 검색 색인이 없으면 이름 검색 안내를 제공하며 의미 검색으로 위장한 임의 결과는 반환하지 않는다.

규칙 지원 플래그와 공식 출처 검토를 구분한다. 공식 출처 확인은 `config/source-reviews.json`의 `official_verified`와 문서 SHA-256이 일치하는 경우에만 표시한다. 색인된 것만으로 지원 플래그를 자동 승격하지 않는다.

## 검증

- 백엔드: 기존 테스트와 조건 경계값·명시 필터 우선·실제 mock 벡터 색인 검색·확장 호환성·진행 요청 복원·원문 접근 권한·경로 탈출 차단 테스트 46개 통과.
- 실제 로컬 DB 읽기 확인: 4명·30분 이하 게임 53개, 첫 페이지 12개. 코드네임 상세 응답 200, 판본 1개, 공식 출처 확인 상태 검증. 이 확인은 외부 모델을 호출하지 않는다.
- 프론트: TypeScript, ESLint, Prettier 검사 통과. Playwright가 production build 후 실행된다.
- 브라우저: **14개 통과, 56.6초**. 모바일/데스크톱에서 질문·상황 판정·근거·원문 다운로드·게임 전환·새로고침·진행 요청 재개·실패 재시도·되묻기·근거 부족·조건 검색·모션 감소·세션 만료·불명확한 전송의 중복 방지를 검증했다. 초기 테스트의 포커스 검증과 장르 선택자를 수정하고 최종 전체 실행에서 통과했다.
- 360/768/1440px에서 가로 넘침이 없음을 검사했다. 모바일 대화·근거 및 데스크톱·태블릿 캡처를 직접 확인했다. 처음 캡처에서 발견한 주사위 글꼴 대체 문제를 SVG로 수정했다.
- ChromaDB의 Python 3.16 예정 deprecation 경고 1개와 브라우저 실행 도구의 색상 환경변수 경고가 있었으며 테스트 실패는 아니다.
- 자동 테스트의 답변·임베딩은 격리된 가상 자료와 대체 응답이다. 이번 단계에서 실제 GMS 질문 전송이나 전체 110개 게임의 답변 품질 평가는 수행하지 않았다.

## 재현

검증 화면: [모바일 대화와 근거](stage4-screenshots/mobile-citation.png), [360px 탐색](stage4-screenshots/mobile-360.png), [태블릿](stage4-screenshots/tablet-768.png), [데스크톱 대화와 근거](stage4-screenshots/desktop-citation.png), [1440px 탐색](stage4-screenshots/desktop-1440.png).

저장소 루트에서 `corepack pnpm typecheck`, `corepack pnpm lint`, `corepack pnpm format:check`, `corepack pnpm test:e2e`를 실행한다. API 폴더에서 `.venv/Scripts/python.exe -m pytest -q`와 `.venv/Scripts/ruff.exe check rule_u tests`를 실행한다.

Playwright는 별도 임시 DB와 8100/3100 포트를 사용한다. 기존 개발 DB를 변경하지 않는다. Windows 제한 계정에서 테스트 서버 종료 권한이 없으면 종료가 지연될 수 있어, 해당 실행에서는 테스트 프로세스 트리를 확인·정리하고 정상 종료 권한으로 재실행했다.

## 남은 범위

실제 모델을 통한 새 UI의 답변 품질 평가, 모든 게임의 공식 출처·이용 조건 검토, 5단계 하이브리드/MMR 비교는 별도다. 수집·색인은 기존 CLI를 사용하며 화면에서 신규 수집 작업을 시작하지 않는다.
