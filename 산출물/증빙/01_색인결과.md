# 2단계 수집·색인 결과

2026-10-22. 기본 수집·색인 단계의 구현과 초기 검증을 완료했다. 110개 게임을 모두 공식 규칙으로 인증했다는 의미는 아니다. 사용자 제공 문서·미확인 출처·이미지 정리 전사의 한계는 계속 유지한다.

## 구현

- `rule_u.discovery inventory`: 110게임·117문서의 출처, 언어, 판본, 확장 확인 상태, 이용 조건, 원본 해시, 추출 상태 목록을 생성한다. [목록](./source-inventory.json)과 [출처 검토](../config/source-reviews.json)는 버전 관리한다. 검토는 정확한 원본 해시에 연결되며 파일이 바뀌면 확인 상태를 재사용하지 않는다.
- `discover`: 프롬프트 1로 검색어 JSON을 생성하고 프롬프트 2로 등록 공식 후보 ID를 선별한다. 각각 최대 두 번 시도하며 파싱 실패 시 결정적인 대체 경로를 사용한다. 모델이 생성한 URL이나 다른 게임·판본의 ID는 수집 대상이 될 수 없다. 선택 게임의 자체 규칙서는 출처가 미확인이어도 출처 구분을 유지하면서 항상 포함한다.
- 캐시 범위는 게임·판본·확장·질문·맥락·등록 출처 전체 스냅샷·모델 설정이다. `--collect --bundle-root ..`는 확보된 문서 묶음에서 선택된 문서만 기존 해시 검사·추출 흐름으로 처리한다. 형제 문서의 manifest를 보존한다. 인터넷 전체를 검색하거나 새 PDF를 임의로 내려받는 기능은 아니다.
- PDF 물리 페이지·FAQ 질문/답변 단위·원문 위치·1,000자/200자 청킹을 유지한다. 이미지 복원 세부 사항은 [복원 보고서](../reports/visual-recovery-report.md)에 있다.

## 공식 출처 초기 확인

초기 확보 후보를 실제 보유 자료에 맞춰 코드네임·식스 님트·7원더스 건축가들로 정했다. 카탄은 사용자 제공 자료로 유지하며 다른 판본의 공식 문서로 대체하지 않았다.

- 코드네임: [CGE 게임 페이지](https://www.czechgames.com/games/codenames)와 [한국어 PDF](https://filemanager.czechgames.com/storage/files/codenames/rules/codenames-rules-ko.pdf)를 확인했다.
- 식스 님트: [AMIGO 공식 다운로드 목록](https://blog.amigo-spiele.de/content/ws/plenty.php?id=4910&select=downloads)의 한국어 링크가 등록 URL과 일치한다. 웹 도구의 PDF 직접 읽기는 시간 초과였으며 보유 파일의 시각 검토 기록을 사용한다.
- 7원더스 건축가들: [Repos 공식 페이지](https://www.rprod.com/en/games/7-wonders-architects)의 KR 링크가 등록 URL과 일치한다. 웹 도구의 PDF 크기 제한으로 보유 파일의 시각 검토 기록을 사용한다.

공식 다운로드 경로 확인과 저작물의 자유 재배포 허가는 별개다. 세 문서의 정확한 인쇄 쇄 및 포괄적 재배포·임베딩 라이선스는 확인하지 못했으며 목록에 명시했다. 나머지 114문서는 이번 초기 검증에서 공식성을 인증하지 않았다. 확장 적용 관계도 미확인 항목을 임의로 확정하지 않았다.

## 검증

- 실제 GMS 인덱스: 110게임·2,541청크. 추가 임베딩을 금지한 전체 재실행과 청크 집합·문자 오프셋·페이지·벡터 검사는 `data/stage2-idempotency.json`, `data/stage2-audit.json`에 기록한다.
- 자연어 질문 8개, 5게임: 정답 문서·페이지를 미리 지정한 [평가 입력](../evals/retrieval-smoke-cases.json) 기준 **페이지 Hit@5 8/8, MRR@5 0.78125**. 게임·판본 필터를 적용했다. 단일 페이지 쿠 설명서는 평가가 쉬운 사례이며 표본이 작아 전체 110게임 품질을 대표하지 않는다.
- 질문 임베딩 캐시: 반복 실행 8/8 적중. 캐시 실행 평균 검색 시간 약 0.042초(단일 로컬 실행). 첫 기록은 6개 기존 캐시와 2개 신규 질문이 섞인 실행이므로 전부 신규인 실행 시간으로 보고하지 않는다.
- 실제 채팅 모델의 검색어 추출·후보 선별은 코드네임 질문에서 두 프롬프트 모두 대체 경로 없이 성공했고, 동일 요청 재실행은 캐시에 적중했다.
- pytest 27개, Ruff, Alembic check 통과. 캐시 변경 감지, 판본 격리, 허위 ID 거부, 필수 자체 문서 보존, 오류 시 대체 처리, 선택되지 않은 manifest 보존을 검사했다.

이 평가는 근거 페이지 검색 검사다. 답변 생성·인용 정확성 평가와 웹 RAG 연결은 3단계에서 구현하며, 전체 게임의 공식 출처 확인과 게임당 평가 질문 확대·검색 방식 비교는 5단계에서 계속한다.

## 실행 예시

저장소 루트에서 API 가상환경 Python으로 실행한다.

```powershell
python -m rule_u.discovery inventory --catalog ../data/games --reviews config/source-reviews.json --output reports/source-inventory.json
python -m rule_u.discovery discover --catalog ../data/games --reviews config/source-reviews.json --game codenames --edition codenames-official-ko-rulebook --question "암살자를 고르면 어떻게 되나요?" --output data/discovery-result.json
python -m rule_u.discovery evaluate --catalog ../data/games --cases evals/retrieval-smoke-cases.json --output data/retrieval-evaluation.json
python apps/api/tools/validate_stage2.py
```

이미지 복원 문서 수집에는 `--reviewed-pages data/retry-reports/vision/reviewed-bound.json`을 추가한다. 수집 이후 실제 색인은 기존 `rule_u.cli index` 명령으로 수행한다. 후보 캐시·원문 추출 캐시·인덱스 상태는 서로 다른 기록이다.
