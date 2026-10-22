# Rule_U

보드게임 규칙 탐색·상황 판정 서비스의 로컬 모노레포입니다. 현재 **1단계 기반 구현**까지 진행했습니다. 실제 규칙 수집·검색·판정은 2~3단계에서 연결합니다.

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

## 설정과 실제 연결 검증

루트 `.env`를 사용하며 상대 `RULE_U_DATA_DIR`은 실행 위치와 관계없이 저장소 루트 기준입니다. 기본 데이터는 `data/app.db`, `data/chroma`, `data/originals`, `data/extracted`에 저장됩니다. ChromaDB 색인 구현은 2단계입니다. 실제 데이터와 `.env`는 Git에서 제외합니다.

`../streamlit_lab/step6_context.py`에서 확인한 호출 규격:

- 주소: `https://gms.ssafy.io/gmsapi/api.openai.com/v1/`
- 모델 ID: `gpt-5.4-nano`
- 인증: `GMS_KEY`를 Bearer 키로 전달
- 요청: `POST chat/completions`에 `model`, 역할별 `messages`

이는 기존 문서의 `5.6 Sol` 표시 이름과 별개입니다. 예제의 실제 모델 ID만 기본값으로 사용했습니다. 예제 폴더에는 `.env.example`만 있고 실제 `.env`는 없었습니다. 키 값은 복사하거나 출력하지 않았습니다.

기본값은 외부 호출 없는 `mock`입니다. 실제 채팅 연결을 확인하려면 루트 `.env`에서 다음 값을 설정합니다:

```dotenv
RULE_U_CHAT_PROVIDER=compatible
RULE_U_CHAT_API_KEY=발급받은_키
# RULE_U_CHAT_API_KEY 대신 GMS_KEY도 사용 가능
```

`RULE_U_CHAT_API_KEY`가 설정되어 있으면 `GMS_KEY`보다 우선합니다. `GMS_KEY`를 쓸 때는 빈 `RULE_U_CHAT_API_KEY` 줄을 삭제하세요. 서버는 다른 프로젝트의 `.env`를 자동으로 읽지 않습니다.

임베딩은 별도 제공업체·키·모델을 설정합니다. 제공업체에서 지원하는 모델 ID와 실제 차원을 확인한 후 아래 값을 입력합니다. GMS의 임베딩 지원 여부는 아직 확인되지 않았습니다.

```dotenv
RULE_U_EMBEDDING_PROVIDER=compatible
RULE_U_EMBEDDING_BASE_URL=확인한_API_주소
RULE_U_EMBEDDING_MODEL=확인한_모델_ID
RULE_U_EMBEDDING_API_KEY=발급받은_키
RULE_U_EMBEDDING_DIMENSIONS=확인한_차원수
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
uv run python -m rule_u.cli export-openapi
Set-Location ../..
corepack pnpm types:api
corepack pnpm typecheck
corepack pnpm build
corepack pnpm test:e2e
```

E2E는 설치된 Microsoft Edge를 headless로 사용합니다. 8100·3100 포트에서 임시 DB와 웹 서버를 띄우고 종료합니다. 실제 `data/app.db`는 사용하지 않습니다. 데스크톱·모바일 크기에서 게임 선택, 질문 저장, 새로고침 후 복원과 가로 넘침을 확인합니다. 화면 캡처는 Git에서 제외되는 `test-results/`에 생성됩니다. E2E 후 기본 API 포트로 production 실행하려면 `corepack pnpm build`를 다시 실행하세요.

검증 결과와 미완료 사항은 [개발계획](docs/개발계획.md)의 단계 1 기록에서 관리합니다.

## 저장 구조와 구현 범위

```text
Rule_U/
  apps/web/             Next.js 화면·동일 출처 프록시·생성된 API 타입
  apps/api/rule_u/      설정·모델·API·독립 모델/임베딩 연결부·CLI
  apps/api/migrations/ Alembic 버전 고정 스키마
  apps/api/tests/      저장·접근·요청·연결부 테스트
  tests/e2e/           브라우저 통합 검증
  docs/                기능명세서·개발계획
  data/                로컬 DB·원문·추출문·색인 (Git 제외)
```

게임·판본·확장·문서·적용 범위·수집 상태·대화·메시지·인용·요청과 판본/확장 연결 테이블을 저장합니다. 판본과 게임 일치, 확장 호환, 외부 게임 ID 중복, 기본판 문서 범위 중복, 요청 중복, 대화당 진행 중 요청 1개를 DB 제약으로 검증합니다. 인용 제목·출처·판본·페이지·문서 버전은 스냅샷으로 보존합니다.

현재 API: health, games 목록/상세, conversations 생성/조회, messages 제출(202), requests 조회. 자연어 게임 검색·실제 근거 조회·RAG·수집·색인은 후속 단계입니다. 아직 공식 규칙을 확보하지 않았으므로 모든 게임의 규칙 지원 상태는 false입니다.

구현 참고: [Next.js 설치](https://nextjs.org/docs/app/getting-started/installation), [SQLAlchemy SQLite](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html), [FastAPI 앱 구조](https://fastapi.tiangolo.com/tutorial/bigger-applications/).
