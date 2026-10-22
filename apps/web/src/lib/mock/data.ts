import type { Schema } from "../api";

export type MockGame = Schema["GameDetail"] & {
  /** 이름 검색에 함께 쓰이는 원제·별칭 (백엔드 name_original, aliases). */
  aliases: string[];
};

export type MockScenario = {
  /** 질문에 하나라도 포함되면 이 시나리오로 응답합니다. */
  keywords: string[];
  answer: string;
  verdict: string;
  citations: Omit<Schema["SourceOut"], "id">[];
};

export const games: MockGame[] = [
  {
    id: "game-catan",
    name_ko: "카탄",
    aliases: ["Catan", "카탄의 개척자"],
    description: "자원을 모아 정착지와 도시를 건설하는 전략 게임",
    min_players: 3,
    max_players: 4,
    min_minutes: 60,
    max_minutes: 120,
    categories: ["전략", "협상"],
    rules_supported: true,
    source_review: "official_verified",
    editions: [
      {
        id: "ed-catan-ko-5",
        label: "한국어판 5판",
        language: "ko",
        supported: true,
      },
      {
        id: "ed-catan-en-5",
        label: "English 5th Edition",
        language: "en",
        supported: false,
      },
    ],
    expansions: [
      {
        id: "exp-catan-seafarers",
        name: "항해사",
        supported: true,
        edition_ids: ["ed-catan-ko-5"],
      },
      {
        id: "exp-catan-cities",
        name: "도시와 기사",
        supported: false,
        edition_ids: ["ed-catan-ko-5"],
      },
    ],
  },
  {
    id: "game-splendor",
    name_ko: "스플렌더",
    aliases: ["Splendor"],
    description: "보석 토큰으로 개발 카드를 구매해 명성을 얻는 게임",
    min_players: 2,
    max_players: 4,
    min_minutes: 30,
    max_minutes: 30,
    categories: ["전략", "카드"],
    rules_supported: true,
    source_review: "unverified",
    editions: [
      {
        id: "ed-splendor-ko",
        label: "한국어판",
        language: "ko",
        supported: true,
      },
    ],
    expansions: [],
  },
  {
    id: "game-codenames",
    name_ko: "코드네임",
    aliases: ["Codenames"],
    description: "스파이마스터의 힌트로 우리 팀 요원을 찾는 단어 게임",
    min_players: 2,
    max_players: 8,
    min_minutes: 15,
    max_minutes: 15,
    categories: ["파티", "단어"],
    rules_supported: true,
    source_review: "official_verified",
    editions: [
      {
        id: "ed-codenames-ko",
        label: "한국어판",
        language: "ko",
        supported: true,
      },
    ],
    expansions: [],
  },
  {
    id: "game-empty",
    name_ko: "판본 없는 게임",
    aliases: [],
    description: "판본 미등록 상태 확인용",
    min_players: 1,
    max_players: 5,
    min_minutes: 0,
    max_minutes: 0,
    categories: [],
    rules_supported: false,
    source_review: "unverified",
    editions: [],
    expansions: [],
  },
];

const catanRule = {
  document_id: "doc-catan-rule",
  title: "카탄 공식 규칙서",
  edition: "한국어판 5판",
  url: "https://example.com/catan-rules.pdf",
  source_version: "v1",
  source_type: "official_rulebook",
  language: "ko",
  extraction_method: "pdf_text",
  review_note: "",
  // 원문 링크는 실제 API 경로라 목 모드에서는 숨깁니다.
  original_available: false,
  explanation: null,
  source_review: "official_verified",
};

export const scenarios: MockScenario[] = [
  {
    keywords: ["도둑", "7"],
    answer:
      "주사위 합이 7이면 손에 자원 카드가 8장 이상인 플레이어는 절반(내림)을 버립니다 [1]. 그 후 주사위를 굴린 플레이어가 도둑을 옮기고 인접 플레이어에게서 카드 1장을 가져옵니다 [2].",
    verdict: "allowed",
    citations: [
      {
        ...catanRule,
        number: 1,
        page_start: 6,
        page_end: 6,
        excerpt:
          "7이 나오면 자원 카드를 8장 이상 가진 모든 플레이어는 가진 카드의 절반을 골라 버립니다. 홀수이면 내림합니다.",
      },
      {
        ...catanRule,
        number: 2,
        page_start: 6,
        page_end: 7,
        excerpt:
          "주사위를 굴린 플레이어는 도둑을 다른 지형 타일로 옮기고, 그 타일에 정착지나 도시가 있는 플레이어 1명에게서 무작위로 자원 카드 1장을 가져옵니다.",
      },
    ],
  },
  {
    keywords: ["교역", "거래"],
    answer:
      "자신의 차례에만 다른 플레이어와 교역할 수 있으며, 다른 플레이어끼리는 교역할 수 없습니다 [1]. 상대의 차례에는 그 플레이어가 제안한 교역에만 응할 수 있습니다.",
    verdict: "conditional",
    citations: [
      {
        ...catanRule,
        number: 1,
        page_start: 8,
        page_end: null,
        excerpt:
          "교역은 자신의 차례에만 할 수 있습니다. 차례가 아닌 플레이어끼리는 서로 교역할 수 없습니다.",
      },
    ],
  },
  {
    keywords: ["건설"],
    answer: "다른 플레이어의 차례에는 건설할 수 없습니다 [1].",
    verdict: "not_allowed",
    citations: [
      {
        ...catanRule,
        number: 1,
        page_start: 9,
        page_end: null,
        excerpt: "건설은 자신의 차례의 교역·건설 단계에서만 할 수 있습니다.",
      },
    ],
  },
  {
    keywords: ["카드"],
    answer:
      "어떤 카드를 말씀하시는지 알려주세요. 카드 이름과 사용하려는 턴 단계를 알려주시면 판정할 수 있습니다.",
    verdict: "needs_clarification",
    citations: [],
  },
];

export const fallbackScenario: MockScenario = {
  keywords: [],
  answer:
    "현재 확인된 근거만으로는 답변을 확인할 수 없습니다. (목 응답: '도둑', '교역', '건설', '카드', '실패'를 포함해 질문해 보세요.)",
  verdict: "insufficient_evidence",
  citations: [],
};

export const explanation: Schema["SourceExplanationOut"] = {
  rule_summary:
    "목 데이터의 근거 요약입니다. 규칙서의 해당 문단이 말하는 핵심을 짧게 정리합니다.",
  application: "질문한 상황에 이 규칙이 어떻게 적용되는지 설명합니다.",
};
