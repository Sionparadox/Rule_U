import type { components } from "./api.generated";

export type Schema = components["schemas"];
/** NEXT_PUBLIC_API_MOCK=1이면 FastAPI 대신 브라우저 내 목 API를 사용합니다. */
export const API_MOCK = process.env.NEXT_PUBLIC_API_MOCK === "1";
export class ApiError extends Error {
  constructor(
    public code: string,
    public status = 0,
  ) {
    super(code);
  }
}
export async function api<T>(
  path: string,
  body?: unknown,
  signal?: AbortSignal,
  timeoutMs = 15000,
): Promise<T> {
  if (API_MOCK) {
    const { mockFetch } = await import("./mock/handlers");
    return mockFetch<T>(path, body, signal);
  }
  const response = await fetch(`/api/v1${path}`, {
    method: body === undefined ? "GET" : "POST",
    cache: "no-store",
    headers:
      body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: signal
      ? AbortSignal.any([signal, AbortSignal.timeout(timeoutMs)])
      : AbortSignal.timeout(timeoutMs),
  });
  if (!response.ok) {
    const value = await response.json().catch(() => ({}));
    throw new ApiError(
      typeof value.detail === "string" ? value.detail : "invalid_request",
      response.status,
    );
  }
  return response.json();
}
export const errorText = (error: unknown): string => {
  const code = error instanceof ApiError ? error.code : "connection_lost";
  const messages: Record<string, string> = {
    provider_not_configured:
      "답변 서비스 연결 설정이 없습니다. 서비스 설정 후 다시 시도해 주세요.",
    chat_model_missing:
      "답변 모델이 설정되지 않았습니다. 서비스 설정을 확인해 주세요.",
    embedding_model_missing:
      "검색 모델이 설정되지 않았습니다. 이름 검색을 이용해 주세요.",
    invalid_embedding_response_or_dimension:
      "검색 서비스의 응답을 확인할 수 없습니다. 이름 검색을 이용해 주세요.",
    search_index_missing:
      "자연어 검색 자료가 아직 없습니다. 이름 검색을 이용해 주세요.",
    search_unavailable:
      "자연어 검색을 사용할 수 없습니다. 이름 검색을 이용하거나 다시 시도해 주세요.",
    search_timeout: "검색 시간이 초과되었습니다. 다시 검색해 주세요.",
    rules_not_ready:
      "선택한 확장의 규칙이 준비되지 않았습니다. 기본판을 선택해 주세요.",
    incompatible_expansion: "선택한 판본과 호환되지 않는 확장입니다.",
    request_in_progress:
      "이 대화의 답변을 생성하고 있습니다. 처리 상태를 다시 확인해 주세요.",
    provider_call_failed:
      "답변 서비스에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.",
    server_restarted:
      "서비스가 재시작되어 답변이 중단됐습니다. 질문을 다시 시도해 주세요.",
    generation_failed: "답변 생성에 실패했습니다. 질문을 다시 시도해 주세요.",
    conversation_not_found:
      "대화를 찾을 수 없습니다. 게임을 선택해 새 대화를 시작해 주세요.",
    original_unavailable: "로컬 원문을 찾을 수 없습니다.",
    database_unavailable:
      "대화를 저장할 수 없습니다. 서비스 연결을 확인해 주세요.",
  };
  return (
    messages[code] ??
    "연결이 끊겼거나 요청을 처리하지 못했습니다. 다시 시도해 주세요."
  );
};
