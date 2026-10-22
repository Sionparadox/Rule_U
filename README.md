# Rule_U

게임 선택 → 질문·상황 판정 → 출처 설명 모달까지 연결된 로컬 보드게임 규칙 도우미입니다. Next.js·FastAPI·SQLite·ChromaDB를 사용합니다. 전체 게임의 답변 품질 검증은 후속 범위입니다.

업데이트 후 API 폴더에서 `uv sync`와 `uv run alembic upgrade head`를 실행합니다. 질문 API는 확보된 근거를 검색하고 답변과 인용을 저장합니다. 출처는 동일 세션에서만 조회할 수 있습니다. 색인 CLI는 동시에 여러 프로세스로 실행하지 않습니다.

RAG 근거가 부족하면 BGG의 최근 Rules 토론을 추가 조회합니다. 저장소 루트 `.env`에 `BGG_API_TOKEN=승인된_앱_토큰`을 설정하고 API 서버를 재시작하세요. [BGG 앱 등록](https://boardgamegeek.com/applications)·승인이 필요하며 토큰은 채팅이나 Git에 올리지 않습니다. `BGG_ENABLED=false`로 끌 수 있고, 채팅 mock 모드에서는 외부 조회하지 않습니다. BGG 토론은 공식 룰북과 구분하여 표시합니다. [동작·설정·검증 한계](reports/bgg-fallback.md)를 참고하세요.

Next.js App Router + TypeScript / FastAPI / SQLite + SQLAlchemy + Alembic. Windows에서 Docker 없이 실행합니다. 계획과 명세서는 [docs/개발계획.md](docs/개발계획.md), [docs/기능명세서.md](docs/기능명세서.md)에 있습니다.

## 준비

- Node.js 20.9 이상 및 Corepack (`corepack --version`), Python 3.12~3.14, uv.
- pnpm은 `package.json`에 지정된 버전을 `corepack pnpm`으로 실행합니다. 별도 전역 pnpm 설치가 필요하지 않습니다.
- 아래 PowerShell 명령은 `Rule_U` 루트에서 시작합니다.

```powershell
Copy-Item .env.example .env
corepack pnpm install --frozen-lockfile
Set-Location apps/api
uv sync --frozen
uv run alembic upgrade head
uv run python -m rule_u.cli seed-demo
Set-Location ../..
```

`seed-demo`는 가상 게임 1개와 테스트 판본을 중복 없이 저장합니다. 공식 게임·규칙 확보 수에 포함하지 않습니다. DB를 자동으로 생성·수정하는 대신 Alembic을 먼저 실행해야 합니다.

## 실행

터미널 1:

```powershell
Set-Location apps/api
uv run uvicorn rule_u.main:create_app --factory --host 127.0.0.1 --port 8000
```

터미널 2 (저장소 루트):

```powershell
corepack pnpm dev:web
```

- 웹: http://127.0.0.1:3000
- API 문서: http://127.0.0.1:8000/docs
- 상태 확인: http://127.0.0.1:8000/api/v1/health

샘플 게임 선택 → 질문 → 테스트 응답 → 새로고침으로 저장을 확인할 수 있습니다. 쿠키가 같은 브라우저에서 대화를 복원하며 다른 익명 세션에서는 접근을 차단합니다. 현재 UI는 샘플의 첫 판본을 선택합니다. 전체 판본·확장 선택과 게임별 대화 전환 UI는 4단계입니다.

API는 **단일 프로세스**로 실행합니다. 여러 worker를 지정하지 마세요. 시작 시 이전 실행의 미완료 요청을 실패로 복구합니다. Next.js는 `/api/v1`을 FastAPI로 프록시합니다. API 포트 변경 시 웹 실행/빌드 전에 `API_ORIGIN`을 지정하세요. 운영 빌드에서는 빌드 시 프록시 주소가 고정되므로 변경 후 재빌드해야 합니다.

### 프론트엔드 단독 실행 (목 데이터)

API·Python 없이 화면만 개발할 때는 저장소 루트에서 실행합니다:

```powershell
corepack pnpm dev:mock
```

`NEXT_PUBLIC_API_MOCK=1`로 실행되어 모든 `/api/v1` 호출이 [apps/web/src/lib/mock](apps/web/src/lib/mock)의 브라우저 내 목 API로 처리됩니다. 헤더에 `MOCK DATA` 표시가 나타납니다.

- 게임·판본·확장·답변 시나리오는 [data.ts](apps/web/src/lib/mock/data.ts)에서 수정합니다. 질문에 `도둑`(가능+인용 2개), `교역`(조건부), `건설`(불가), `카드`(되묻기), `실패`(생성 실패)가 포함되면 해당 응답을, 그 외에는 근거 부족 응답을 반환합니다.
- 카탄의 `도시와 기사` 확장은 규칙 미준비(`rules_not_ready`) 오류를 확인하는 용도입니다. 자연어 검색은 목에서 이름 검색으로 대체되고, 근거 원문 링크는 표시하지 않습니다.
- 응답 지연, 답변 단계 전환 간격, 근거 설명 생성 시간은 [handlers.ts](apps/web/src/lib/mock/handlers.ts) 상단 상수로 조절합니다.
- 목 대화는 localStorage `rule-u-mock-db`에 저장되어 새로고침 후에도 복원됩니다. 초기화하려면 브라우저 저장소에서 해당 키를 삭제합니다.
- API 호출은 [api.ts](apps/web/src/lib/api.ts)의 `api()`를 사용해야 목 전환이 적용됩니다.

## 설정과 실제 연결 검증

루트 `.env`를 사용하며 상대 `DATA_DIR`은 실행 위치와 관계없이 저장소 루트 기준입니다. 기본 데이터는 `data/app.db`, `data/chroma`, `data/originals`, `data/extracted`에 저장됩니다. 실제 데이터와 `.env`는 Git에서 제외합니다.

`../streamlit_lab/step6_context.py`에서 확인한 호출 규격:

- 주소: `https://gms.ssafy.io/gmsapi/api.openai.com/v1/`
- 모델 ID: `gpt-5.4-nano`
- 인증: `GMS_KEY`를 Bearer 키로 전달
- 요청: `POST chat/completions`에 `model`, 역할별 `messages`

이는 기존 문서의 `5.6 Sol` 표시 이름과 별개입니다. 예제의 실제 모델 ID만 기본값으로 사용했습니다. 예제 폴더에는 `.env.example`만 있고 실제 `.env`는 없었습니다. 키 값은 복사하거나 출력하지 않았습니다.

기본값은 외부 호출 없는 `mock`입니다. 실제 채팅 연결을 확인하려면 루트 `.env`에서 다음 값을 설정합니다:

```dotenv
CHAT_PROVIDER=compatible
CHAT_API_KEY=발급받은_키
# CHAT_API_KEY 대신 GMS_KEY도 사용 가능
```

`CHAT_API_KEY`가 설정되어 있으면 `GMS_KEY`보다 우선합니다. `GMS_KEY`를 쓸 때는 빈 `CHAT_API_KEY` 줄을 삭제하세요. 서버는 다른 프로젝트의 `.env`를 자동으로 읽지 않습니다.

임베딩은 별도 제공업체·키·모델을 설정합니다. 2026-10-22 GMS의 `text-embedding-3-large`를 실제 호출하여 입력 2개에 대한 3,072차원 벡터를 검증했습니다. 로컬 `.env`에는 기존 GMS 키로 다음 설정을 반영했습니다. 키 값은 문서나 설정 예제에 포함하지 않습니다.

```dotenv
EMBEDDING_PROVIDER=compatible
EMBEDDING_BASE_URL=https://gms.ssafy.io/gmsapi/api.openai.com/v1/
EMBEDDING_MODEL=text-embedding-3-large
EMBEDDING_API_KEY=발급받은_키
EMBEDDING_DIMENSIONS=3072
```

`POST embeddings` 호환 요청을 사용합니다. 응답 개수·인덱스·유한 숫자·차원 수를 검증합니다. 다른 규격의 제공업체는 `rule_u/providers.py`의 별도 어댑터로 추가하세요. 모델·차원을 바꾸면 기존 색인을 재생성해야 합니다.

```powershell
Set-Location apps/api
uv run python -m rule_u.cli probe
uv run python -m rule_u.cli probe --live
```

`--live`는 대체 응답을 성공으로 처리하지 않습니다. 두 실제 연결이 모두 확인되지 않으면 종료 코드 1이며 각 연결의 상태를 별도로 출력합니다. 키·전체 응답·외부 오류 본문은 출력하지 않습니다. 실제 모드는 작은 검증 입력을 외부 API로 전송합니다.

실제 모델의 무근거 답변을 규칙 판정처럼 제공하지 않도록 **1단계 웹 질문 흐름은 mock 전용**입니다. 실제 호출은 위 probe 명령에서 검증합니다. `/health`는 로컬 준비 상태이며 실제 연결 인증서는 아닙니다.

## 검증

```powershell
Set-Location apps/api
uv run pytest -q
uv run ruff check rule_u tests migrations
uv run alembic check
Set-Location ../..
corepack pnpm check:api
corepack pnpm typecheck
corepack pnpm build
corepack pnpm test:e2e
```

API 스키마를 바꾼 뒤에는 `corepack pnpm sync:api`로 `openapi.json` 내보내기와 프론트 타입 생성을 한 번에 실행하고 두 파일을 함께 커밋합니다. `check:api`는 동기화 후 두 파일에 변경이 생기면 실패합니다. 갱신을 빠뜨리면 pytest의 `test_committed_openapi_is_current`도 실패합니다.

GitHub Actions([ci.yml](.github/workflows/ci.yml))가 push·PR마다 API 검사(ruff·alembic·pytest), 웹 검사(타입 생성 일치·typecheck·build), E2E를 실행합니다.

E2E는 로컬에서 설치된 Microsoft Edge를 headless로 사용하고, CI(`CI` 환경변수)에서는 Playwright Chromium을 사용합니다. API 서버는 `uv run --project apps/api`로 실행하므로 `uv`가 PATH에 있어야 합니다. 8100·3100 포트에서 임시 DB와 웹 서버를 띄우고 종료합니다. 실제 `data/app.db`는 사용하지 않습니다. 데스크톱·모바일 크기에서 게임 선택, 질문 저장, 새로고침 후 복원과 가로 넘침을 확인합니다. 화면 캡처는 Git에서 제외되는 `test-results/`에 생성됩니다. E2E 후 기본 API 포트로 production 실행하려면 `corepack pnpm build`를 다시 실행하세요.

검증 결과와 미완료 사항은 [개발계획](docs/개발계획.md)의 단계 1 기록에서 관리합니다.

## 저장 구조와 구현 범위

```text
Rule_U/
  apps/web/             Next.js 화면·동일 출처 프록시·생성된 API 타입
  apps/api/rule_u/      설정·모델·API·독립 모델/임베딩 연결부·CLI
  apps/api/migrations/ Alembic 버전 고정 스키마
  apps/api/tests/      저장·접근·요청·연결부 테스트
  tests/e2e/           브라우저 통합 검증
  docs/                개발계획·개발기록·기능명세서
  reports/             작업 결과 보고서·출처 현황 목록
  config/              출처 검토 입력
  evals/               검색 평가 입력
  data/                로컬 DB·원문·추출문·색인 (Git 제외)
```

게임·판본·확장·문서·적용 범위·수집 상태·대화·메시지·인용·요청과 판본/확장 연결 테이블을 저장합니다. 판본과 게임 일치, 확장 호환, 외부 게임 ID 중복, 기본판 문서 범위 중복, 요청 중복, 대화당 진행 중 요청 1개를 DB 제약으로 검증합니다. 인용 제목·출처·판본·페이지·문서 버전은 스냅샷으로 보존합니다.

현재 API: health, games 목록/상세, conversations 생성/조회, messages 제출(202), requests 조회. 자연어 게임 검색·실제 근거 조회·RAG는 후속 단계입니다. 로컬 수집·색인 CLI는 아래와 같습니다. 추출·색인만으로 규칙 지원을 인정하지 않으므로 판본의 지원 상태는 자동으로 true가 되지 않습니다.

## 2단계 로컬 데이터 적재·추출·색인

`apps/api`에서 실행합니다. 아래 경로는 기존 `Core2/data` 묶음을 사용하며 입력 원문과 JSON을 변경하지 않습니다.

```powershell
uv sync --frozen
uv run alembic upgrade head
uv run python -m rule_u.cli import-metadata --catalog ../../../data/games
uv run python -m rule_u.cli ingest --catalog ../../../data/games --bundle-root ../../.. --games codenames abluxxen catan
uv run python -m rule_u.cli index --catalog ../../../data/games --games codenames abluxxen catan --mock
uv run python -m rule_u.cli data-status
```

전체 등록 게임을 처리하려면 `--games`를 생략합니다. 실제 임베딩은 설정된 GMS로 전체 메타데이터·청크를 전송합니다. `--continue-on-error`는 실패한 게임을 기록하고 다음 게임을 계속 처리합니다. 일부 실패가 있으면 모든 게임을 시도한 뒤 종료 코드 1을 반환합니다.

```powershell
uv run python -m rule_u.cli ingest --catalog ../../../data/games --bundle-root ../../..
uv run python -m rule_u.cli index --catalog ../../../data/games --continue-on-error
```

추출 결과는 게임마다 `data/manifests/<slug>.json`, 전체 색인 결과는 `data/index-reports/<모델 지문>-catalog.json`에 저장합니다. 추출 실패·누락 문서가 있는 게임은 규칙 색인을 보류하지만 메타데이터는 색인합니다. 수정 후 같은 명령을 재실행하면 저장된 벡터를 재사용합니다. PDF 글꼴 해석에 `fonttools`를 사용하며, 추출기가 내용 생략을 경고한 문서는 검토 필요로 처리합니다.

전체 실행 결과(2026-10-22): 이미지 복원과 재시도를 반영해 실제 GMS 인덱스에 110게임·2,541청크를 저장했습니다. [2단계 결과](reports/stage2-completion.md)에서 검증 결과와 남은 출처 확인 사항을 확인할 수 있습니다.

기본 PDF 추출기는 `pypdf`입니다. 다이브는 내용 생략 경고가 발생해 `pymupdf`로 복구했습니다. 다음처럼 추출기를 명시해 재현할 수 있으며, 추출기별 결과는 별도 캐시로 보존됩니다. 두 방식 모두 페이지별 20자 미만 검사를 유지하고 OCR은 수행하지 않습니다. 전체를 기본 추출기로 다시 적재했다면 다이브에 아래 명령을 다시 적용하세요.

실패했던 49게임·50문서의 복구 과정은 [이미지 복원 보고서](reports/visual-recovery-report.md)에 있습니다. 자동 진단은 `apps/api`에서 `uv run python -m rule_u.retry_diagnostics --catalog ../../../data/games --bundle-root ../../..`로 실행합니다. 원문·색인을 수정하거나 외부 API를 호출하지 않으며, 진단 JSON과 보고서는 `data/retry-reports/`에 저장합니다.

```powershell
uv run python -m rule_u.cli ingest --catalog ../../../data/games --bundle-root ../../.. --games dive --pdf-extractor pymupdf
uv run python -m rule_u.cli index --catalog ../../../data/games --games dive --mock
```

- `--catalog`: 게임별 JSON 디렉터리, JSON 객체/배열 파일 또는 CSV. CSV의 `players`, `play_time_minutes`, `aliases`, `categories`, `editions`는 같은 스키마의 JSON 문자열 셀입니다. 필수 항목은 `id`, `slug`, `name_ko`, `players.min/max`, `play_time_minutes.min/max`, `editions`입니다. 판본은 `id`, `name`, `language`를 포함합니다.
- `--games`: 처리할 slug 목록. 생략하면 전체를 처리합니다. 입력의 정수 ID는 외부 ID로, slug는 앱의 게임 ID로 보존합니다.
- 문서는 `status=downloaded`, `local_path`, `sha256`이 필요합니다. 파일은 `--bundle-root` 내부로 제한하며 해시가 다르면 실패 처리합니다. FAQ는 `type=faq`와 `[{"question":"...","answer":"..."}]` JSON 파일을 사용하고 질문·답변 단위로 보존합니다.
- 원문은 `data/originals`, 페이지·청크·문자 오프셋은 `data/extracted`, 원래 메타데이터 전체는 `data/catalog`, 게임별 결과는 `data/manifests`에 보존합니다. 출처 유형이 없으면 `unverified`, 이용 조건이 없으면 미확인으로 기록합니다.
- 기본 청크는 1,000자·중복 200자이며 가능한 줄 경계에서 나눕니다. 페이지를 넘는 규칙·예외 결합과 다단 편집 순서의 품질 검토는 후속 작업입니다. 텍스트가 20자 미만인 페이지는 검토 필요로 처리하며 OCR은 수행하지 않습니다.
- `--mock`은 외부 호출 없는 구조 검증용입니다. 실제 의미 검색 품질을 검증하지 않습니다. 생략하면 `.env`의 임베딩 제공업체로 메타데이터와 추출 청크가 전송됩니다. 실제 전송 전에 문서 전송 범위와 제공업체를 확인하세요.
- 임베딩 제공업체·주소·모델·차원별로 Chroma 저장 폴더를 분리하고 `game_meta`, `rule_docs` 컬렉션을 생성합니다. 고정 ID와 내용 해시로 같은 입력의 임베딩 호출을 생략합니다. 추출 설정 변경 시 청크를 다시 만들며 새 청크 저장 후 오래된 청크를 제거합니다.
- 일부 문서가 실패한 게임은 규칙 색인을 거부합니다. 여러 게임의 실행 전체가 원자적이지는 않으며, 새 색인 버전의 활성 전환과 RAG 노출 제어는 3단계 범위입니다. 현재 색인은 웹 답변에 사용하지 않습니다.

2026-10-22 검증: 110개 게임·117개 판본 적재. 코드네임·링코·카탄 13페이지·27청크 추출. 사용자 승인 후 GMS 실제 임베딩으로 메타데이터 3건·규칙 청크 27건을 색인했습니다. 전체 30건의 3,072차원·유한 숫자를 확인했고 재실행 시 추가 임베딩 0건·캐시 30건을 확인했습니다. 저장 벡터를 이용한 자기 검색과 게임 범위 필터도 확인했습니다. 자연어 질문의 검색 품질 평가는 별도이며 공식 출처·이용 조건 검토, 등록 출처 후보 검색·검색어 캐시는 남아 있습니다.

구현 참고: [Next.js 설치](https://nextjs.org/docs/app/getting-started/installation), [SQLAlchemy SQLite](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html), [FastAPI 앱 구조](https://fastapi.tiangolo.com/tutorial/bigger-applications/).
# 현재 데이터·검색 상태 (2026-10-22)

## 4단계 화면 사용

답변의 출처 번호를 누르면 **왜 이렇게 답변했나요?** 모달에서 해당 규칙과 적용 이유를 확인할 수 있습니다. 원문 청크 대신 이해하기 쉬운 설명과 룰북 페이지를 표시합니다. 예전 답변의 설명은 처음 열 때 생성하므로 잠시 기다릴 수 있으며 이후에는 저장된 설명을 사용합니다. 이 기능을 반영하려면 기존 API 서버를 종료한 뒤 다시 실행하세요.

최신 UI는 모바일 게임 런처 형태입니다. 앱을 열거나 새로고침하면 검색창과 파스텔 카드형 게임 선택 화면이 먼저 표시됩니다. 게임 카드 → 판본·확장 선택 팝업 → 채팅 순서로 이동합니다. 저장된 대화는 첫 화면의 **이전 대화 이어하기**로 재개합니다. 답변 대기 중에는 말풍선에 스피너와 스켈레톤이 표시됩니다. [새 화면 캡처](reports/mobile-game-ui.md).

게임 이름이나 자연어로 검색하고 인원·최대 시간·장르 필터를 지정합니다. 게임 카드를 선택한 뒤 판본과 호환 확장을 고르고 **이 게임으로 대화하기**를 누릅니다. **규칙 질문 / 상황 판정** 모드에서 질문하고 답변의 `[1]` 같은 번호를 눌러 근거를 확인합니다. 작은 화면에서는 근거 패널이 접혀 있으며 번호를 누르면 열립니다.

대화는 익명 세션 쿠키와 연결됩니다. 같은 브라우저에서 게임을 전환하거나 새로고침해도 게임·판본·확장 조합별 대화를 복원합니다. 쿠키를 삭제하면 이전 대화에 접근할 수 없습니다. 질문 접수 여부가 불명확할 때는 **전송 다시 확인**, 확정 실패 시에는 **질문 다시 시도**를 사용합니다.

화면은 Next.js·TypeScript·Tailwind CSS·Zustand·Motion으로 구성하고 Pretendard를 로컬 제공합니다. 개발 서버 실행 절차는 기존과 같으며 추가 검사 명령은 다음과 같습니다.

```powershell
corepack pnpm lint
corepack pnpm format:check
corepack pnpm typecheck
corepack pnpm test:e2e
```

API 변경 시 `apps/api`에서 `uv run python -m rule_u.cli export-openapi`, 저장소 루트에서 `corepack pnpm types:api`를 순서대로 실행합니다. 구현·검증 상세는 [4단계 결과](reports/stage4-progress.md)에 있습니다.

아래의 1·2단계 기록 중 테스트 전용 화면·웹 미연결 설명은 당시 상태입니다. 현재 화면은 기존 RAG·인용·상황 판정 API에 연결되며 자연어 게임 탐색 API도 제공합니다. 새로운 실서비스 모델 질문 평가는 이번 단계의 자동 테스트와 구분합니다.

2단계 기본 구현과 초기 검증 완료: 실제 GMS 인덱스 110게임·2,541청크, 질문 8개의 근거 페이지 Hit@5 100%. 전체 공식 출처 인증이나 답변 생성 완료를 의미하지 않는다. 출처 목록·후보 선별·캐시·실행 명령은 [2단계 결과](reports/stage2-completion.md)를 참고한다.

