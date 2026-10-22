"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { useReducedMotion } from "motion/react";
import { api, ApiError, errorText, type Schema } from "@/lib/api";
import { useStore } from "@/lib/store";

const stageLabel: Record<string, string> = {
  queued: "질문 접수됨",
  retrieve: "규칙 근거를 찾고 있어요",
  generate: "답변을 정리하고 있어요",
  completed: "답변 완료",
  failed: "답변 중단",
};
const verdictLabel: Record<string, string> = {
  allowed: "가능해요",
  not_allowed: "할 수 없어요",
  conditional: "조건을 확인해 주세요",
  insufficient_evidence: "근거가 부족해요",
  needs_clarification: "상황을 더 알려주세요",
  unavailable: "테스트 응답",
};

import { Dice } from "./game-art";

export function Chat() {
  const s = useStore();
  const end = useRef<HTMLDivElement>(null);
  const reduced = useReducedMotion();
  const c = s.conversation;
  const rid = c?.active_request_id;
  const cid = c?.id;
  const [pollVersion, setPollVersion] = useState(0);
  const [pollError, setPollError] = useState("");
  useEffect(() => {
    if (!rid || !cid) return;
    const conversationId = cid;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const request = await api<Schema["RequestOut"]>(
          `/requests/${rid}`,
          undefined,
          controller.signal,
        );
        if (
          controller.signal.aborted ||
          useStore.getState().conversation?.id !== conversationId
        )
          return;
        useStore.setState({ request });
        setPollError("");
        if (["completed", "failed"].includes(request.status))
          await useStore.getState().refresh(conversationId);
        else timer = setTimeout(poll, 1000);
      } catch (e) {
        if (!controller.signal.aborted) setPollError(errorText(e));
      }
    }
    void poll();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [rid, cid, pollVersion]);
  useEffect(() => {
    end.current?.scrollIntoView({
      behavior: reduced ? "instant" : "smooth",
      block: "nearest",
    });
  }, [c?.messages.length, s.sending, c?.active_request_id, reduced]);
  const processing = s.sending || !!c?.active_request_id;
  const unresolved = !!(
    c &&
    s.pending[c.id] &&
    s.pending[c.id].client_request_id !== c.latest_client_request_id &&
    !s.sending
  );
  const draft = c ? (s.drafts[c.id] ?? "") : "";
  async function submit(e: FormEvent) {
    e.preventDefault();
    await s.send();
  }
  function showSource(source: Schema["SourceOut"]) {
    useStore.setState({ source, sourcesOpen: true });
  }
  return (
    <section
      className="panel flex h-[calc(100dvh-6.5rem)] min-h-[480px] flex-col overflow-hidden shadow-[0_5px_0_#d3e9e3] sm:h-[calc(100dvh-8rem)]"
      aria-label="규칙 대화"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line p-5">
        <div>
          <p className="text-xs font-semibold text-felt">플레이 메이트</p>
          <h2 className="mt-1 text-lg font-bold">
            {c
              ? s.chatDetail?.id === c.game_id
                ? s.chatDetail.name_ko
                : "규칙 이야기"
              : "플레이를 이어가세요"}
          </h2>
        </div>
        {c && (
          <button
            className="btn"
            onClick={() => useStore.setState({ view: "games" })}
          >
            게임 변경
          </button>
        )}
      </div>
      {c && (
        <div className="border-b border-line px-5 py-3">
          <p className="mb-3 text-xs text-ink/65">
            {s.chatDetail?.editions.find((e) => e.id === c.edition_id)?.label ??
              c.edition_id}
            {c.expansion_ids.length
              ? ` · 확장 ${c.expansion_ids.length}개`
              : " · 기본판"}
          </p>
          <div
            className="flex w-fit rounded-xl bg-table p-1"
            role="group"
            aria-label="질문 모드"
          >
            {(
              [
                ["qa", "규칙 질문"],
                ["ruling", "상황 판정"],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                disabled={processing}
                className={`relative min-h-10 rounded-lg px-4 text-sm font-semibold ${s.mode === value ? "bg-felt text-white" : "text-ink/65"}`}
                aria-pressed={s.mode === value}
                onClick={() => useStore.setState({ mode: value })}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      )}
      <div
        className="flex-1 space-y-6 overflow-y-auto overscroll-contain p-5 md:p-7"
        aria-live="polite"
        aria-relevant="additions text"
      >
        {!c?.messages.length && (
          <div className="flex min-h-64 flex-col items-center justify-center px-3 text-center">
            <div
              aria-hidden
              className="mb-6 flex size-16 rotate-[-8deg] items-center justify-center rounded-2xl border-2 border-felt bg-table text-4xl text-felt"
            >
              <Dice />
            </div>
            <h3 className="text-xl font-bold">
              {c ? "헷갈리는 순간, 물어보세요" : "규칙 때문에 멈추지 않도록"}
            </h3>
            <p className="mt-3 max-w-xs text-sm leading-7 text-ink/65">
              {c
                ? s.mode === "ruling"
                  ? "하려는 행동, 현재 턴, 관련 카드를 알려주세요. 필요한 정보가 더 있으면 물어볼게요."
                  : "준비 방법부터 예외 규칙까지, 선택한 판본의 근거와 함께 확인해요."
                : "게임과 판본을 선택하면 질문을 시작할 수 있어요. 답변 옆에서 규칙서도 함께 확인하세요."}
            </p>
          </div>
        )}
        {c?.messages.map((m) => (
          <article
            key={m.id}
            className={
              m.role === "user"
                ? "ml-auto max-w-[90%] rounded-2xl rounded-br-sm bg-felt px-4 py-3 text-white"
                : "mr-auto max-w-[95%] rounded-[22px] rounded-bl-sm bg-[#f0f8f5] p-4"
            }
          >
            <p
              className={`mb-2 text-xs font-semibold ${m.role === "user" ? "text-white/75" : "text-felt"}`}
            >
              {m.role === "user"
                ? m.mode === "ruling"
                  ? "나 · 상황 판정"
                  : "나"
                : "Rule_U"}
            </p>
            {m.role !== "user" && m.verdict && (
              <p className="mb-2 text-sm font-bold text-token">
                {verdictLabel[m.verdict] ?? m.verdict}
              </p>
            )}
            <p className="whitespace-pre-wrap break-words text-[15px] leading-7">
              {m.content.split(/(\[\d+\])/g).map((part, index) => {
                const number = /^\[(\d+)\]$/.exec(part);
                const source = number
                  ? m.citations?.find((v) => v.number === Number(number[1]))
                  : null;
                return source ? (
                  <button
                    key={index}
                    className="mx-1 inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg bg-table font-semibold text-felt underline"
                    aria-label={`근거 ${source.number} 보기`}
                    onClick={() => showSource(source)}
                  >
                    {part}
                  </button>
                ) : (
                  part
                );
              })}
            </p>
            {m.role !== "user" && !m.citations?.length && (
              <p className="mt-3 text-xs text-ink/60">
                이 답변에 인용된 근거가 없습니다.
              </p>
            )}
          </article>
        ))}
        {processing && (
          <div
            role="status"
            aria-label="답변을 생각하고 있어요"
            className="mr-auto w-[85%] max-w-sm rounded-[22px] rounded-bl-sm bg-[#f0f8f5] p-4 text-sm text-felt"
          >
            <div className="mb-4 flex items-center gap-2 font-semibold">
              <span className="spinner" aria-hidden />
              {stageLabel[
                s.sending ? "queued" : (s.request?.stage ?? "queued")
              ] ?? "답변을 생각하고 있어요"}
            </div>
            <div aria-hidden className="space-y-2.5">
              <div className="skeleton-line w-full" />
              <div className="skeleton-line w-4/5" />
              <div className="skeleton-line w-2/5" />
            </div>
          </div>
        )}
        {s.request?.status === "failed" && !unresolved && (
          <div role="alert" className="rounded-xl bg-orange-50 p-4 text-sm">
            <p>
              {errorText(
                new ApiError(s.request.error_code ?? "generation_failed"),
              )}
            </p>
            <button
              className="btn mt-3"
              disabled={s.sending}
              onClick={() => void s.send(true)}
            >
              질문 다시 시도
            </button>
          </div>
        )}
        {pollError && (
          <div role="alert" className="text-sm text-red-800">
            {pollError}
            <button
              className="btn ml-2"
              onClick={() => setPollVersion((v) => v + 1)}
            >
              처리 상태 다시 확인
            </button>
          </div>
        )}
        {s.error && (
          <div role="alert" className="text-sm text-red-800">
            <p>{s.error}</p>
          </div>
        )}
        {unresolved && !processing && (
          <div role="status" className="rounded-xl bg-table p-4 text-sm">
            <p>이전 질문의 접수 여부를 확인한 뒤 새 질문을 보낼 수 있어요.</p>
            <button className="btn mt-2" onClick={() => void s.send(true)}>
              전송 다시 확인
            </button>
          </div>
        )}
        <div ref={end} />
      </div>
      <form
        onSubmit={submit}
        className="sticky bottom-0 border-t border-line bg-white p-4 pb-[max(1rem,env(safe-area-inset-bottom))]"
      >
        <div className="flex items-end gap-2">
          <label className="flex-1">
            <span className="sr-only">규칙 질문</span>
            <textarea
              rows={2}
              className="w-full"
              value={draft}
              disabled={!c || processing || unresolved}
              maxLength={8000}
              placeholder={
                s.mode === "ruling"
                  ? "지금 상황과 하려는 행동을 알려주세요"
                  : "궁금한 규칙을 물어보세요"
              }
              onChange={(e) =>
                c &&
                useStore.setState({
                  drafts: { ...s.drafts, [c.id]: e.target.value },
                })
              }
            />
          </label>
          <button
            className="btn-primary mb-1 size-12 shrink-0 text-xl"
            type="submit"
            aria-label="질문 보내기"
            disabled={!c || processing || unresolved || !draft.trim()}
          >
            ↑
          </button>
        </div>
        <p className="mt-2 text-[11px] text-ink/60">
          선택한 판본을 기준으로 답해요. 중요한 판정은 원문도 확인해 주세요.
        </p>
      </form>
    </section>
  );
}
