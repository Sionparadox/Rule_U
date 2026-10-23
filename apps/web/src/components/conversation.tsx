"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  AnimatePresence,
  motion,
  stagger,
  useReducedMotion,
} from "motion/react";
import { exitQuick, playful, quick, rise, settle } from "@/lib/motion";
import { api, ApiError, errorText, type Schema } from "@/lib/api";
import { useStore } from "@/lib/store";
import { BrandMark, RollingDice } from "./marks";
import {
  AnswerActions,
  composeSituation,
  emptySituation,
  QuestionStarters,
  SavedRulesSheet,
  SituationHelper,
  SourceBadge,
  type Situation,
} from "./answer-tools";

const stageLabel: Record<string, string> = {
  queued: "질문 접수됨",
  retrieve: "규칙 근거를 찾고 있어요",
  bgg: "BGG에서 추가 근거를 확인하고 있어요",
  generate: "답변을 정리하고 있어요",
  completed: "답변 완료",
  failed: "답변 중단",
};

// 판정은 말 색 + 기호 + 문구로 함께 알린다 (색만으로 구분하지 않는다).
const symbols = {
  check: "m6 12.5 4 4 8-9",
  cross: "m7 7 10 10m0-10L7 17",
  bang: "M12 6v7.5M12 17.5v.5",
  ask: "M9.2 9a2.9 2.9 0 1 1 4.1 2.7c-.8.4-1.3 1-1.3 1.9v.4M12 17.5v.5",
  dash: "M7 12h10",
};
const verdicts: Record<
  string,
  { label: string; card: string; symbol: keyof typeof symbols }
> = {
  allowed: { label: "가능해요", card: "bg-green", symbol: "check" },
  not_allowed: { label: "할 수 없어요", card: "bg-red", symbol: "cross" },
  conditional: {
    label: "조건을 확인해 주세요",
    card: "bg-yellow",
    symbol: "bang",
  },
  insufficient_evidence: {
    label: "근거가 부족해요",
    card: "bg-surface-soft",
    symbol: "dash",
  },
  needs_clarification: {
    label: "상황을 더 알려주세요",
    card: "bg-surface-soft",
    symbol: "ask",
  },
  unavailable: {
    label: "테스트 응답",
    card: "bg-surface-soft",
    symbol: "dash",
  },
};

function Token({ symbol }: { symbol: keyof typeof symbols }) {
  return (
    <span className="flex size-10 shrink-0 items-center justify-center rounded-full border-[2.5px] border-ink bg-surface">
      <svg
        aria-hidden
        viewBox="0 0 24 24"
        className="size-6"
        fill="none"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d={symbols[symbol]} />
      </svg>
    </span>
  );
}

const pageText = (source: Schema["SourceOut"]) =>
  source.page_start
    ? `${source.page_start}${source.page_end && source.page_end !== source.page_start ? `–${source.page_end}` : ""}쪽`
    : "쪽 정보 없음";

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
  const [situation, setSituation] = useState<Situation>(emptySituation);
  const [situationOpen, setSituationOpen] = useState(false);
  const [savedOpen, setSavedOpen] = useState(false);
  const situationText = composeSituation(situation, "");
  const ready = !!(draft.trim() || (s.mode === "ruling" && situationText));
  function setDraft(value: string) {
    if (c)
      useStore.setState((state) => ({
        drafts: { ...state.drafts, [c.id]: value },
      }));
  }
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!c) return;
    const ruling = s.mode === "ruling" && !!situationText;
    // 상황 정리 칸의 값을 질문 앞에 붙여 한 번에 보낸다.
    if (ruling) setDraft(composeSituation(situation, draft));
    await s.send();
    if (ruling && !useStore.getState().error) {
      setSituation(emptySituation);
      setSituationOpen(false);
    }
  }
  // 기다리는 동안 경과 시간을 보여 주고, BGG 추가 검색은 중단할 수 있게 한다.
  const [elapsed, setElapsed] = useState(0);
  const [skipping, setSkipping] = useState(false);
  const [waiting, setWaiting] = useState(processing);
  if (waiting !== processing) {
    // 새 대기가 시작되거나 끝나면 경과 시간과 중단 상태를 처음으로 돌린다.
    setWaiting(processing);
    setElapsed(0);
    setSkipping(false);
  }
  useEffect(() => {
    if (!processing) return;
    const timer = setInterval(() => setElapsed((v) => v + 1), 1000);
    return () => clearInterval(timer);
  }, [processing]);
  async function skipExternal() {
    if (!rid) return;
    setSkipping(true);
    try {
      await api(`/requests/${rid}/skip-external`, {});
    } catch {
      setSkipping(false);
    }
  }
  function showSource(source: Schema["SourceOut"]) {
    useStore.setState({ source, sourcesOpen: true });
  }
  const game =
    s.chatDetail && c && s.chatDetail.id === c.game_id ? s.chatDetail : null;
  // 화면을 열 때 이미 있던 메시지는 움직이지 않고, 새로 도착한 메시지만 등장 효과를 준다.
  const [seen, setSeen] = useState<{ id?: string; messages: Set<string> }>({
    messages: new Set(),
  });
  if (c && seen.id !== c.id)
    setSeen({ id: c.id, messages: new Set(c.messages.map((m) => m.id)) });
  const fresh = (id: string) => seen.id === c?.id && !seen.messages.has(id);
  const stage =
    stageLabel[s.sending ? "queued" : (s.request?.stage ?? "queued")] ??
    "답변을 생각하고 있어요";
  return (
    <section
      className="flex h-[calc(100dvh-5rem)] min-h-[480px] flex-col overflow-hidden rounded-[28px] bg-surface shadow-[0_4px_0_var(--color-edge)] sm:h-[calc(100dvh-6rem)]"
      aria-label="규칙 대화"
    >
      <div className="px-3 pt-3 pb-3 sm:px-4">
        <div className="flex items-center gap-3">
          {c && (
            <button
              className="icon-round"
              aria-label="게임 변경"
              onClick={() => useStore.setState({ view: "games" })}
            >
              <svg
                aria-hidden
                viewBox="0 0 20 20"
                className="size-5"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M12.5 4.5 7 10l5.5 5.5" />
              </svg>
            </button>
          )}
          <div className="min-w-0 flex-1">
            <h2 className="font-game truncate text-[22px] leading-tight">
              {c ? (game?.name_ko ?? "규칙 이야기") : "플레이를 이어가세요"}
            </h2>
            {c && (
              <p className="truncate text-xs text-muted">
                {s.chatDetail?.editions.find((e) => e.id === c.edition_id)
                  ?.label ?? c.edition_id}
                {c.expansion_ids.length
                  ? `, 확장 ${c.expansion_ids.length}개`
                  : ", 기본판"}
              </p>
            )}
          </div>
          {c && (
            <button
              className="icon-round"
              aria-label="저장한 규칙"
              onClick={() => setSavedOpen(true)}
            >
              <svg
                aria-hidden
                viewBox="0 0 20 20"
                className="size-5"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
                strokeLinejoin="round"
              >
                <path d="M5.5 3.5h9v13l-4.5-3-4.5 3z" />
              </svg>
            </button>
          )}
        </div>
        {c && (
          <div
            className="mt-3 grid grid-cols-2 gap-1 rounded-2xl bg-surface-soft p-1"
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
                className={`font-game relative min-h-11 rounded-xl text-base transition-colors ${s.mode === value ? "text-blue" : "text-muted"}`}
                aria-pressed={s.mode === value}
                onClick={() => useStore.setState({ mode: value })}
              >
                {s.mode === value && (
                  // 선택 표시가 고른 쪽으로 미끄러져 간다.
                  <motion.span
                    layoutId="mode-pill"
                    transition={settle}
                    className="absolute inset-0 rounded-xl bg-surface shadow-[0_3px_0_var(--color-edge)]"
                  />
                )}
                <span className="relative">{label}</span>
              </button>
            ))}
          </div>
        )}
      </div>
      <div
        className="flex-1 space-y-4 overflow-y-auto overscroll-contain bg-ground px-3 py-4 sm:px-5"
        aria-live="polite"
        aria-relevant="additions text"
      >
        {!c?.messages.length && (
          <div className="flex min-h-64 flex-col items-center justify-center px-3 text-center">
            <BrandMark className="mb-4 size-16" />
            <h3 className="font-game text-2xl">
              {c ? "헷갈리는 순간, 물어보세요" : "규칙 때문에 멈추지 않도록"}
            </h3>
            <p className="mt-2 max-w-xs text-sm leading-6 text-muted">
              {c
                ? s.mode === "ruling"
                  ? "하려는 행동, 현재 턴, 관련 카드를 알려주세요. 정보가 더 필요하면 되물어볼게요."
                  : "준비 방법부터 예외 규칙까지, 선택한 판본의 근거와 함께 답해요."
                : "게임과 판본을 고르면 질문을 시작할 수 있어요."}
            </p>
            {c && (
              <QuestionStarters
                game={game?.name_ko ?? "이 게임"}
                onPick={(text) => {
                  useStore.setState({ mode: "qa" });
                  setDraft(text);
                  document
                    .querySelector<HTMLTextAreaElement>(
                      "textarea[name=question]",
                    )
                    ?.focus();
                }}
              />
            )}
          </div>
        )}
        {c?.messages.map((m) =>
          m.role === "user" ? (
            <motion.article
              key={m.id}
              initial={
                fresh(m.id) ? { opacity: 0, x: 16, y: 8, scale: 0.96 } : false
              }
              animate={{ opacity: 1, x: 0, y: 0, scale: 1 }}
              transition={quick}
              style={{ transformOrigin: "bottom right" }}
              className="ml-auto w-fit max-w-[85%] rounded-3xl rounded-br-lg bg-blue px-4 py-3 text-white"
            >
              <p className="text-xs font-semibold text-white/85">
                {m.mode === "ruling" ? "나, 상황 판정 요청" : "나"}
              </p>
              <p className="text-[15px] leading-7 break-words whitespace-pre-wrap">
                {m.content}
              </p>
            </motion.article>
          ) : (
            <motion.article
              key={m.id}
              initial={fresh(m.id) ? { opacity: 0, y: 14 } : false}
              animate={{ opacity: 1, y: 0 }}
              transition={quick}
              className="mr-auto w-full max-w-[96%] overflow-hidden rounded-3xl bg-surface shadow-[0_4px_0_var(--color-edge)]"
            >
              {m.verdict ? (
                <div
                  className={`flex items-center gap-3 px-4 py-3 text-ink ${verdicts[m.verdict]?.card ?? "bg-surface-soft"}`}
                >
                  {/* 판정 토큰이 테이블에 놓이듯 튀며 내려앉는다. 답변마다 한 번뿐인 순간. */}
                  <motion.span
                    initial={
                      fresh(m.id)
                        ? { scale: 0.4, rotate: -24, opacity: 0 }
                        : false
                    }
                    animate={{ scale: 1, rotate: 0, opacity: 1 }}
                    transition={{ ...playful, delay: 0.1 }}
                  >
                    <Token symbol={verdicts[m.verdict]?.symbol ?? "dash"} />
                  </motion.span>
                  <motion.p
                    initial={fresh(m.id) ? { opacity: 0, x: -6 } : false}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ ...quick, delay: 0.14 }}
                    className="font-game text-[22px] leading-tight"
                  >
                    <span className="sr-only">Rule_U 판정: </span>
                    {verdicts[m.verdict]?.label ?? m.verdict}
                  </motion.p>
                </div>
              ) : (
                <p className="flex items-center gap-2 px-4 pt-3 text-xs font-semibold text-blue">
                  <BrandMark className="size-5" />
                  Rule_U
                </p>
              )}
              <p className="px-4 py-3 text-[15px] leading-7 break-words whitespace-pre-wrap">
                {m.content.split(/(\[\d+\])/g).map((part, index) => {
                  const number = /^\[(\d+)\]$/.exec(part);
                  const source = number
                    ? m.citations?.find((v) => v.number === Number(number[1]))
                    : null;
                  return source ? (
                    <button
                      key={index}
                      className="font-game relative mx-0.5 inline-flex h-6 min-w-6 -translate-y-0.5 items-center justify-center rounded-lg bg-blue px-1.5 align-middle text-sm text-white after:absolute after:-inset-2.5"
                      aria-label={`근거 ${source.number} 보기`}
                      onClick={() => showSource(source)}
                    >
                      {source.number}
                    </button>
                  ) : (
                    part
                  );
                })}
              </p>
              {m.citations?.length ? (
                <motion.div
                  initial={fresh(m.id) ? "hidden" : false}
                  animate="shown"
                  variants={{
                    hidden: {},
                    shown: {
                      transition: {
                        delayChildren: stagger(0.05, { startDelay: 0.22 }),
                      },
                    },
                  }}
                  className="flex flex-wrap gap-2 px-4 pt-1 pb-4"
                >
                  {m.citations.map((source) => (
                    <motion.div
                      key={source.id}
                      variants={rise}
                      className="max-w-full"
                    >
                      <button
                        className="chunky flex min-h-11 max-w-full items-center gap-2 rounded-2xl border-[1.5px] border-edge bg-surface py-1.5 pr-3 pl-1.5 text-left text-sm [--depth:3px]"
                        aria-label={`출처 ${source.number} 자세히`}
                        onClick={() => showSource(source)}
                      >
                        <span className="font-game flex size-7 shrink-0 items-center justify-center rounded-lg bg-blue text-white">
                          {source.number}
                        </span>
                        <span className="min-w-0 truncate font-semibold">
                          {source.title}
                        </span>
                        <span className="shrink-0 text-xs text-muted">
                          {pageText(source)}
                        </span>
                        <SourceBadge source={source} />
                      </button>
                    </motion.div>
                  ))}
                </motion.div>
              ) : (
                <p className="px-4 pb-4 text-xs text-muted">
                  이 답변에 인용된 근거가 없습니다.
                </p>
              )}
              {m.verdict === "needs_clarification" && (
                <div className="px-4 pb-3">
                  <button
                    className="btn-soft"
                    onClick={() => {
                      useStore.setState({ mode: "ruling" });
                      setSituationOpen(true);
                    }}
                  >
                    상황 정리해서 답하기
                  </button>
                </div>
              )}
              {m.verdict !== "unavailable" && <AnswerActions message={m} />}
            </motion.article>
          ),
        )}
        <AnimatePresence>
          {processing && (
            <motion.div
              key="thinking"
              role="status"
              aria-label="답변을 생각하고 있어요"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, transition: exitQuick }}
              transition={quick}
              className="mr-auto w-[85%] max-w-sm rounded-3xl bg-surface p-4 shadow-[0_4px_0_var(--color-edge)]"
            >
              <div className="font-game mb-4 flex items-center gap-3 text-lg text-blue">
                <RollingDice />
                {/* 단계가 바뀌면 문구가 위로 밀려나며 바뀐다. */}
                <AnimatePresence mode="popLayout" initial={false}>
                  <motion.span
                    key={stage}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8, transition: exitQuick }}
                    transition={quick}
                  >
                    {stage}
                  </motion.span>
                </AnimatePresence>
              </div>
              <div aria-hidden className="space-y-2.5">
                <div className="skeleton-line w-full" />
                <div className="skeleton-line w-4/5" />
                <div className="skeleton-line w-2/5" />
              </div>
              <p className="mt-3 text-xs text-muted" data-testid="elapsed">
                {elapsed}초 지났어요
                {elapsed >= 15
                  ? " · 기다리는 동안 다음 질문을 적어 둘 수 있어요"
                  : ""}
              </p>
              {s.request?.stage === "bgg" && (
                <button
                  className="btn-soft mt-3"
                  disabled={skipping || s.request.skip_external}
                  onClick={() => void skipExternal()}
                >
                  {skipping || s.request.skip_external
                    ? "추가 검색을 멈추는 중…"
                    : "추가 검색 중단"}
                </button>
              )}
            </motion.div>
          )}
        </AnimatePresence>
        {s.request?.status === "failed" && !unresolved && (
          <div role="alert" className="rounded-3xl bg-red/15 p-4 text-sm">
            <p className="font-semibold">
              {errorText(
                new ApiError(s.request.error_code ?? "generation_failed"),
              )}
            </p>
            <button
              className="btn-soft mt-3"
              disabled={s.sending}
              onClick={() => void s.send(true)}
            >
              질문 다시 시도
            </button>
          </div>
        )}
        {pollError && (
          <div role="alert" className="rounded-3xl bg-red/15 p-4 text-sm">
            <p className="font-semibold">{pollError}</p>
            <button
              className="btn-soft mt-3"
              onClick={() => setPollVersion((v) => v + 1)}
            >
              처리 상태 다시 확인
            </button>
          </div>
        )}
        {s.error && (
          <div
            role="alert"
            className="rounded-3xl bg-red/15 p-4 text-sm font-semibold"
          >
            <p>{s.error}</p>
          </div>
        )}
        {unresolved && !processing && (
          <div role="status" className="rounded-3xl bg-yellow/30 p-4 text-sm">
            <p className="font-semibold">
              이전 질문의 접수 여부를 확인한 뒤 새 질문을 보낼 수 있어요.
            </p>
            <button className="btn-soft mt-3" onClick={() => void s.send(true)}>
              전송 다시 확인
            </button>
          </div>
        )}
        <div ref={end} />
      </div>
      <form
        onSubmit={submit}
        className="bg-surface p-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] sm:px-4"
      >
        {c && s.mode === "ruling" && (
          <SituationHelper
            open={situationOpen}
            value={situation}
            onToggle={() => setSituationOpen((v) => !v)}
            onChange={setSituation}
          />
        )}
        <div className="flex items-end gap-2">
          <label className="flex-1">
            <span className="sr-only">규칙 질문</span>
            <textarea
              rows={2}
              name="question"
              autoComplete="off"
              className="w-full"
              value={draft}
              disabled={!c || unresolved}
              maxLength={8000}
              placeholder={
                processing
                  ? "답변을 기다리는 동안 다음 질문을 적어 두세요…"
                  : s.mode === "ruling"
                    ? "지금 상황과 하려는 행동을 알려주세요…"
                    : "궁금한 규칙을 물어보세요…"
              }
              onChange={(e) => setDraft(e.target.value)}
            />
          </label>
          <button
            className="btn-primary mb-1 size-13 shrink-0 p-0"
            type="submit"
            aria-label="질문 보내기"
            disabled={!c || processing || unresolved || !ready}
          >
            <svg
              aria-hidden
              viewBox="0 0 20 20"
              className="size-6"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M10 16V4m-5 5 5-5 5 5" />
            </svg>
          </button>
        </div>
        <p className="mt-2 text-xs text-muted">
          선택한 판본 기준으로 답해요. 중요한 판정은 원문도 확인해 주세요.
        </p>
      </form>
      {savedOpen && c && (
        <SavedRulesSheet
          gameId={c.game_id}
          onClose={() => setSavedOpen(false)}
          onSource={showSource}
        />
      )}
    </section>
  );
}
