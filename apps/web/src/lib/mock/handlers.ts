import { ApiError, type Schema } from "../api";
import {
  explanation,
  fallbackScenario,
  games,
  scenarios,
  type MockGame,
} from "./data";

/** 목 응답 지연(ms). 로딩 상태 확인용. */
const LATENCY = 300;
/** 답변 단계(queued → retrieve → generate → completed)가 바뀌는 간격(ms). */
const STAGE_TIME = 1200;
/** 근거 설명 생성에 걸리는 시간(ms). */
const EXPLANATION_TIME = 1000;
const STORAGE_KEY = "rule-u-mock-db";
const STAGES = ["queued", "retrieve", "generate"];
/** 질문에 "BGG"가 있으면 추가 검색 단계를 이 시간(ms)만큼 유지합니다. 중단 버튼 확인용. */
const BGG_TIME = 30000;

type Conversation = Omit<
  Schema["ConversationOut"],
  "active_request_id" | "latest_request_id" | "latest_client_request_id"
>;
type MockRequest = {
  id: string;
  conversation_id: string;
  client_request_id: string;
  created: number;
  question: string;
  mode: string;
  result_message_id: string | null;
  fail: boolean;
  bgg?: boolean;
  skip_external?: boolean;
};
type MockDb = {
  conversations: Record<string, Conversation>;
  /** 생성 순서대로 저장합니다. */
  requests: MockRequest[];
  citations: Record<string, Schema["SourceOut"]>;
  feedback?: Record<string, Schema["FeedbackOut"]>;
  /** message_id → game_id */
  saved?: Record<string, { game_id: string; saved_at: string }>;
};

// 새로고침 후 대화 복원을 확인할 수 있도록 localStorage에 보관합니다.
function load(): MockDb {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) return JSON.parse(saved);
  } catch {
    /* 저장소 사용 불가 시 빈 DB */
  }
  return { conversations: {}, requests: [], citations: {} };
}
function save(db: MockDb) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(db));
  } catch {
    /* 무시 */
  }
}

const fail = (code: string, status = 404): never => {
  throw new ApiError(code, status);
};

function omit<T extends object, K extends keyof T>(
  value: T,
  ...keys: K[]
): Omit<T, K> {
  const copy = { ...value };
  for (const key of keys) delete copy[key];
  return copy;
}

function summary(game: MockGame): Schema["GameOut"] {
  return omit(game, "editions", "expansions", "aliases");
}

function filtered(
  query: string,
  players?: number | null,
  maxMinutes?: number | null,
  category = "",
) {
  const q = query.trim().toLowerCase();
  return games.filter(
    (g) =>
      (!q || [g.name_ko, ...g.aliases].join(" ").toLowerCase().includes(q)) &&
      (players == null ||
        (g.min_players <= players && players <= g.max_players)) &&
      (maxMinutes == null ||
        (0 < g.max_minutes && g.max_minutes <= maxMinutes)) &&
      (!category || (g.categories ?? []).includes(category)),
  );
}

function page(rows: MockGame[], pageNo = 1, pageSize = 12): Schema["GameList"] {
  return {
    items: rows.slice((pageNo - 1) * pageSize, pageNo * pageSize).map(summary),
    page: pageNo,
    page_size: pageSize,
    total: rows.length,
  };
}

// 경과 시간에 따라 단계를 진행하고 완료 시 답변을 기록합니다 (백엔드의 BackgroundTasks 대응).
function settle(db: MockDb, row: MockRequest): Schema["RequestOut"] {
  const step = Math.floor((Date.now() - row.created) / STAGE_TIME);
  const base = {
    request_id: row.id,
    error_code: null,
    result: null,
    skip_external: !!row.skip_external,
    diagnostic: null,
  };
  if (step < STAGES.length)
    return {
      ...base,
      status: step ? "running" : "queued",
      stage: STAGES[step],
    };
  const external =
    row.bgg &&
    !row.result_message_id &&
    !row.skip_external &&
    Date.now() - row.created < STAGE_TIME * STAGES.length + BGG_TIME;
  if (external) return { ...base, status: "running", stage: "bgg" };
  if (row.fail)
    return {
      ...base,
      status: "failed",
      stage: "failed",
      error_code: "generation_failed",
    };

  const conversation = db.conversations[row.conversation_id];
  if (!row.result_message_id) {
    const found =
      scenarios.find((s) => s.keywords.some((k) => row.question.includes(k))) ??
      fallbackScenario;
    const scenario = row.bgg
      ? {
          ...found,
          verdict: "insufficient_evidence",
          citations: [],
          answer: row.skip_external
            ? "현재 확인된 근거만으로는 답변을 확인할 수 없습니다.\n\nBGG 추가 검색을 중단했어요. 확보된 규칙서 근거만으로는 답을 확인하지 못했어요."
            : "현재 확인된 근거만으로는 답변을 확인할 수 없습니다.\n\nBGG의 최근 규칙 토론에서도 관련 근거를 찾지 못했어요.",
        }
      : found;
    const ids = scenario.citations.map((c) => {
      const id = crypto.randomUUID();
      db.citations[id] = { ...c, id };
      return id;
    });
    const message: Schema["MessageOut"] = {
      id: crypto.randomUUID(),
      role: "assistant",
      content: scenario.answer,
      verdict: scenario.verdict,
      mode: row.mode,
      created_at: new Date().toISOString(),
      cited_source_ids: ids,
      saved: false,
    };
    conversation.messages.push(message);
    row.result_message_id = message.id;
    save(db);
  }
  const message = conversation.messages.find(
    (m) => m.id === row.result_message_id,
  )!;
  const citations = (message.cited_source_ids ?? []).map(
    (id) => db.citations[id],
  );
  return {
    ...base,
    status: "completed",
    stage: "completed",
    result: {
      answer: message.content,
      verdict: message.verdict,
      citations,
      citation_notice: citations.length
        ? ""
        : "이 답변에 인용된 근거가 없습니다.",
    },
  };
}

function conversationOut(db: MockDb, id: string): Schema["ConversationOut"] {
  const conversation = db.conversations[id] ?? fail("conversation_not_found");
  const requests = db.requests.filter((r) => r.conversation_id === id);
  const states = requests.map((r) => settle(db, r));
  const latest = requests.at(-1);
  return {
    ...conversation,
    messages: conversation.messages.map((m) => ({
      ...m,
      citations: (m.cited_source_ids ?? []).map((cid) => db.citations[cid]),
      feedback: db.feedback?.[m.id] ?? null,
      saved: !!db.saved?.[m.id],
    })),
    active_request_id:
      requests.find((_, i) => ["queued", "running"].includes(states[i].status))
        ?.id ?? null,
    latest_request_id: latest?.id ?? null,
    latest_client_request_id: latest?.client_request_id ?? null,
  };
}

async function route(
  path: string,
  body: unknown,
  signal?: AbortSignal,
): Promise<unknown> {
  const db = load();
  const [pathname, search = ""] = path.split("?");
  const [, resource, id, sub] = pathname.split("/");

  if (resource === "health") {
    return {
      status: "ok",
      database: "mock",
      chat_provider: "mock",
      embedding_provider: "mock",
      live_connections_verified: false,
      rules_ready: true,
    } satisfies Schema["HealthOut"];
  }
  if (resource === "game-categories") {
    return [...new Set(games.flatMap((g) => g.categories ?? []))].sort();
  }
  if (resource === "games" && sub === "saved-rules") {
    const items: Schema["SavedRuleOut"][] = [];
    for (const [mid, value] of Object.entries(db.saved ?? {})) {
      if (value.game_id !== id) continue;
      const conversation = Object.values(db.conversations).find((c) =>
        c.messages.some((m) => m.id === mid),
      );
      if (!conversation) continue;
      const index = conversation.messages.findIndex((m) => m.id === mid);
      const message = conversation.messages[index];
      const question = conversation.messages
        .slice(0, index)
        .reverse()
        .find((m) => m.role === "user");
      items.push({
        message_id: mid,
        conversation_id: conversation.id,
        edition_id: conversation.edition_id,
        question: question?.content ?? "",
        answer: message.content,
        verdict: message.verdict,
        saved_at: value.saved_at,
        citations: (message.cited_source_ids ?? []).map(
          (cid) => db.citations[cid],
        ),
      });
    }
    items.sort((a, b) => b.saved_at.localeCompare(a.saved_at));
    return { items } satisfies Schema["SavedRuleList"];
  }
  if (resource === "messages" && (sub === "feedback" || sub === "bookmark")) {
    const conversation =
      Object.values(db.conversations).find((c) =>
        c.messages.some((m) => m.id === id),
      ) ?? fail("message_not_found");
    const message = conversation.messages.find((m) => m.id === id)!;
    if (message.role !== "assistant") fail("assistant_message_required", 422);
    if (sub === "feedback") {
      const input = body as Schema["FeedbackIn"];
      const wrong = input.rating === "wrong";
      const value: Schema["FeedbackOut"] = {
        rating: input.rating,
        reason: wrong ? (input.reason ?? null) : null,
        note: wrong ? (input.note ?? "").trim() : "",
      };
      db.feedback = { ...db.feedback, [id]: value };
      save(db);
      return value;
    }
    const input = body as Schema["BookmarkIn"];
    const saved = { ...db.saved };
    if (input.saved)
      saved[id] = saved[id] ?? {
        game_id: conversation.game_id,
        saved_at: new Date().toISOString(),
      };
    else delete saved[id];
    db.saved = saved;
    save(db);
    return {
      message_id: id,
      saved: input.saved,
    } satisfies Schema["BookmarkOut"];
  }
  if (resource === "requests" && sub === "skip-external") {
    const row =
      db.requests.find((r) => r.id === id) ?? fail("request_not_found");
    if (!["queued", "running"].includes(settle(db, row).status))
      fail("request_not_running", 409);
    row.skip_external = true;
    save(db);
    return { request_id: row.id, status: "running" };
  }
  if (resource === "games" && id === "search") {
    // 자연어 검색은 목에서 이름 검색으로 대체합니다.
    const input = body as Schema["GameSearchIn"];
    return page(
      filtered(input.query, input.players, input.max_minutes, input.category),
      input.page,
      input.page_size,
    );
  }
  if (resource === "games" && !id) {
    const q = new URLSearchParams(search);
    const num = (key: string) => (q.has(key) ? Number(q.get(key)) : null);
    return page(
      filtered(
        q.get("query") ?? "",
        num("players"),
        num("max_minutes"),
        q.get("category") ?? "",
      ),
      num("page") ?? 1,
      num("page_size") ?? 12,
    );
  }
  if (resource === "games") {
    const game = games.find((g) => g.id === id) ?? fail("game_not_found");
    return omit(game, "aliases") satisfies Schema["GameDetail"];
  }
  if (resource === "conversations" && !id && body) {
    const input = body as Schema["ConversationIn"];
    const game =
      games.find((g) => g.id === input.game_id) ?? fail("game_not_found");
    if (!game.editions.some((e) => e.id === input.edition_id))
      fail("invalid_scope", 422);
    const chosen = game.expansions.filter((x) =>
      input.expansion_ids?.includes(x.id),
    );
    if (chosen.some((x) => !x.edition_ids?.includes(input.edition_id)))
      fail("incompatible_expansion", 422);
    if (chosen.some((x) => !x.supported)) fail("rules_not_ready", 422);
    const conversation: Conversation = {
      id: crypto.randomUUID(),
      game_id: input.game_id,
      edition_id: input.edition_id,
      expansion_ids: input.expansion_ids ?? [],
      messages: [],
    };
    db.conversations[conversation.id] = conversation;
    save(db);
    return {
      conversation_id: conversation.id,
    } satisfies Schema["ConversationCreated"];
  }
  if (resource === "conversations" && sub === "messages" && body) {
    const conversation = db.conversations[id] ?? fail("conversation_not_found");
    const input = body as Schema["MessageIn"];
    const requests = db.requests.filter((r) => r.conversation_id === id);
    const existing = requests.find(
      (r) => r.client_request_id === input.client_request_id,
    );
    if (existing)
      return { request_id: existing.id, status: settle(db, existing).status };
    if (
      requests.some((r) => ["queued", "running"].includes(settle(db, r).status))
    )
      fail("request_in_progress", 409);
    const row: MockRequest = {
      id: crypto.randomUUID(),
      conversation_id: id,
      client_request_id: input.client_request_id,
      created: Date.now(),
      question: input.message,
      mode: input.mode,
      result_message_id: null,
      fail: input.message.includes("실패"),
      bgg: input.message.includes("BGG"),
    };
    conversation.messages.push({
      id: crypto.randomUUID(),
      role: "user",
      content: input.message,
      verdict: null,
      mode: input.mode,
      created_at: new Date().toISOString(),
      cited_source_ids: [],
      saved: false,
    });
    db.requests.push(row);
    save(db);
    return {
      request_id: row.id,
      status: "queued",
    } satisfies Schema["RequestAccepted"];
  }
  if (resource === "conversations" && id) return conversationOut(db, id);
  if (resource === "requests") {
    const row =
      db.requests.find((r) => r.id === id) ?? fail("request_not_found");
    return settle(db, row);
  }
  if (resource === "sources" && sub === "explanation") {
    const citation = db.citations[id] ?? fail("source_not_found");
    await wait(EXPLANATION_TIME, signal);
    citation.explanation = explanation;
    save(db);
    return citation;
  }
  if (resource === "sources")
    return db.citations[id] ?? fail("source_not_found");
  return fail(`mock_route_not_found: ${path}`);
}

function wait(ms: number, signal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener("abort", () => {
      clearTimeout(timer);
      reject(signal.reason);
    });
  });
}

export async function mockFetch<T>(
  path: string,
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  await wait(LATENCY, signal);
  // 호출 측에서 응답을 변경해도 목 DB에 영향이 없도록 복사합니다.
  return structuredClone(await route(path, body, signal)) as T;
}
