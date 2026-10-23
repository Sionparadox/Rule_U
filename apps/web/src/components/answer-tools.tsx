"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { api, errorText, type Schema } from "@/lib/api";
import { exitQuick, quick } from "@/lib/motion";
import { useStore } from "@/lib/store";
import { DragSheet } from "./drag-sheet";

type Source = Schema["SourceOut"];
type Message = Schema["MessageOut"];

/** 출처 종류: 모달을 열기 전에도 공식 자료인지 판단할 수 있게 색과 문구를 함께 보여준다. */
export function sourceKind(source: Source) {
  if (source.source_type === "bgg_community")
    return { label: "BGG 커뮤니티", dot: "bg-yellow" };
  if (source.extraction_method?.startsWith("assistant_visual"))
    return { label: "정리 전사", dot: "bg-blue" };
  if (source.source_review === "official_verified")
    return { label: "공식 확인", dot: "bg-green" };
  return { label: "출처 미확인", dot: "bg-edge" };
}

export function SourceBadge({ source }: { source: Source }) {
  const kind = sourceKind(source);
  return (
    <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-surface-soft px-2 py-0.5 text-[11px] font-semibold text-muted">
      <span aria-hidden className={`size-2 rounded-full ${kind.dot}`} />
      {kind.label}
    </span>
  );
}

/** 대화 안의 메시지 하나를 서버 응답으로 갱신한다. */
function patchMessage(id: string, update: Partial<Message>) {
  useStore.setState((s) =>
    s.conversation
      ? {
          conversation: {
            ...s.conversation,
            messages: s.conversation.messages.map((m) =>
              m.id === id ? { ...m, ...update } : m,
            ),
          },
        }
      : {},
  );
}

const reasons = [
  ["rule_differs", "룰북과 달라요"],
  ["wrong_page", "출처 페이지가 맞지 않아요"],
  ["missing_info", "중요한 조건이 빠졌어요"],
  ["other", "기타"],
] as const;
type Reason = (typeof reasons)[number][0];

export function AnswerActions({ message }: { message: Message }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState<Reason>(
    (message.feedback?.reason as Reason | undefined) ?? "rule_differs",
  );
  const [note, setNote] = useState(message.feedback?.note ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const rating = message.feedback?.rating;
  async function rate(value: "helpful" | "wrong") {
    setBusy(true);
    setError("");
    try {
      const feedback = await api<Schema["FeedbackOut"]>(
        `/messages/${message.id}/feedback`,
        value === "wrong"
          ? { rating: value, reason, note: note.trim() }
          : { rating: value },
      );
      patchMessage(message.id, { feedback });
      setOpen(false);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  async function toggleSaved() {
    setBusy(true);
    setError("");
    try {
      const value = await api<Schema["BookmarkOut"]>(
        `/messages/${message.id}/bookmark`,
        { saved: !message.saved },
      );
      patchMessage(message.id, { saved: value.saved });
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="border-t border-surface-soft px-4 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <button
          className={`chip ${rating === "helpful" ? "chip-on" : ""}`}
          aria-pressed={rating === "helpful"}
          disabled={busy}
          onClick={() => void rate("helpful")}
        >
          도움됐어요
        </button>
        <button
          className={`chip ${rating === "wrong" ? "chip-on" : ""}`}
          aria-pressed={rating === "wrong"}
          aria-expanded={open}
          disabled={busy}
          onClick={() => setOpen((v) => !v)}
        >
          규칙이 달라요
        </button>
        <button
          className={`chip ml-auto ${message.saved ? "chip-on" : ""}`}
          aria-pressed={!!message.saved}
          disabled={busy}
          onClick={() => void toggleSaved()}
        >
          <svg
            aria-hidden
            viewBox="0 0 16 16"
            className="size-3.5"
            fill={message.saved ? "currentColor" : "none"}
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinejoin="round"
          >
            <path d="M4 2.5h8v11l-4-2.6-4 2.6z" />
          </svg>
          {message.saved ? "저장됨" : "규칙 저장"}
        </button>
      </div>
      {rating === "wrong" && !open && (
        <p className="mt-2 text-xs text-muted">
          알려주셔서 고마워요. 평가 자료로 검토할게요.
        </p>
      )}
      <AnimatePresence initial={false}>
        {open && (
          <motion.fieldset
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0, transition: exitQuick }}
            transition={quick}
            className="mt-3 overflow-hidden"
          >
            <legend className="mb-2 text-sm font-semibold">
              어떤 점이 다른가요?
            </legend>
            <div className="flex flex-wrap gap-2">
              {reasons.map(([value, label]) => (
                <label
                  key={value}
                  className={`chip cursor-pointer ${reason === value ? "chip-on" : ""}`}
                >
                  <input
                    type="radio"
                    name={`reason-${message.id}`}
                    className="sr-only"
                    checked={reason === value}
                    onChange={() => setReason(value)}
                  />
                  {label}
                </label>
              ))}
            </div>
            <label className="mt-3 block text-sm">
              <span className="sr-only">추가 설명</span>
              <textarea
                rows={2}
                maxLength={500}
                className="w-full"
                placeholder="예: 룰북 7쪽에는 2장이라고 적혀 있어요 (선택)"
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
            </label>
            <button
              className="btn-soft mt-2"
              disabled={busy}
              onClick={() => void rate("wrong")}
            >
              보내기
            </button>
          </motion.fieldset>
        )}
      </AnimatePresence>
      {error && (
        <p role="alert" className="mt-2 text-xs font-semibold text-red-deep">
          {error}
        </p>
      )}
    </div>
  );
}

const verdictText: Record<string, string> = {
  allowed: "가능",
  not_allowed: "불가",
  conditional: "조건부",
  needs_clarification: "추가 정보 필요",
  insufficient_evidence: "근거 부족",
};

export function SavedRulesSheet({
  gameId,
  onClose,
  onSource,
}: {
  gameId: string;
  onClose: () => void;
  onSource: (source: Source) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [items, setItems] = useState<Schema["SavedRuleOut"][] | null>(null);
  const [error, setError] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);
  useEffect(() => {
    const element = dialog.current;
    if (element && !element.open) element.showModal();
    const controller = new AbortController();
    api<Schema["SavedRuleList"]>(
      `/games/${encodeURIComponent(gameId)}/saved-rules`,
      undefined,
      controller.signal,
    )
      .then((value) => setItems(value.items))
      .catch((e) => {
        if (!controller.signal.aborted) setError(errorText(e));
      });
    return () => controller.abort();
  }, [gameId]);
  return (
    <dialog
      ref={dialog}
      aria-labelledby="saved-title"
      className="sheet w-[calc(100%-2rem)] max-w-xl overflow-hidden overscroll-contain rounded-[28px] border-0 bg-surface p-0 text-ink shadow-sheet"
      onClose={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget) dialog.current?.close();
      }}
    >
      <DragSheet
        onDismiss={() => dialog.current?.close()}
        handle={
          <div className="flex items-center justify-between gap-4 bg-blue px-5 py-3.5 text-white">
            <h2 id="saved-title" className="font-game text-lg">
              저장한 규칙
            </h2>
            <button
              autoFocus
              className="icon-round [--depth-color:var(--color-blue-deep)]"
              aria-label="저장한 규칙 닫기"
              onClick={() => dialog.current?.close()}
            >
              <svg
                aria-hidden
                viewBox="0 0 16 16"
                className="size-4"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
              >
                <path d="m4 4 8 8m0-8-8 8" />
              </svg>
            </button>
          </div>
        }
      >
        <div className="max-h-[70dvh] overflow-y-auto p-4 sm:p-5">
          {error ? (
            <p role="alert" className="text-sm font-semibold">
              {error}
            </p>
          ) : items === null ? (
            <div
              role="status"
              aria-label="저장한 규칙을 불러오는 중"
              className="space-y-3"
            >
              <div className="skeleton-line w-full" />
              <div className="skeleton-line w-3/5" />
            </div>
          ) : !items.length ? (
            <p className="text-sm leading-6 text-muted">
              아직 저장한 규칙이 없어요. 자주 확인하는 답변 아래의 규칙 저장을
              눌러 보세요.
            </p>
          ) : (
            <ul className="space-y-2">
              {items.map((item) => (
                <li key={item.message_id} className="rounded-2xl bg-ground">
                  <button
                    className="w-full rounded-2xl p-3 text-left"
                    aria-expanded={openId === item.message_id}
                    onClick={() =>
                      setOpenId((v) =>
                        v === item.message_id ? null : item.message_id,
                      )
                    }
                  >
                    <span className="text-xs font-semibold text-blue">
                      {item.verdict
                        ? (verdictText[item.verdict] ?? item.verdict)
                        : "답변"}
                    </span>
                    <span className="mt-0.5 block font-semibold">
                      {item.question || "질문"}
                    </span>
                  </button>
                  {openId === item.message_id && (
                    <div className="px-3 pb-3">
                      <p className="text-sm leading-6 break-words whitespace-pre-wrap">
                        {item.answer}
                      </p>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {(item.citations ?? []).map((source) => (
                          <button
                            key={source.id}
                            className="chip"
                            onClick={() => {
                              dialog.current?.close();
                              onSource(source);
                            }}
                          >
                            {source.number}. {source.title}
                            <SourceBadge source={source} />
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </DragSheet>
    </dialog>
  );
}

/** 빈 대화에서 자주 묻는 질문을 초안으로 채운다. 바로 보내지 않아 수정할 수 있다. */
export function QuestionStarters({
  game,
  onPick,
}: {
  game: string;
  onPick: (text: string) => void;
}) {
  const starters = [
    ["처음 세팅", `${game} 처음 세팅은 어떻게 하나요?`],
    ["내 차례에 할 일", `${game}에서 내 차례에는 무엇을 순서대로 하나요?`],
    ["점수 계산", `${game} 점수는 어떻게 계산하나요?`],
    ["게임 종료 조건", `${game}은 언제 끝나고 승자는 어떻게 정하나요?`],
    [
      "자주 틀리는 규칙",
      `${game}에서 자주 헷갈리거나 틀리는 규칙은 무엇인가요?`,
    ],
  ];
  return (
    <div
      className="mt-5 flex max-w-md flex-wrap justify-center gap-2"
      role="group"
      aria-label="질문 예시"
    >
      {starters.map(([label, text]) => (
        <button key={label} className="chip" onClick={() => onPick(text)}>
          {label}
        </button>
      ))}
    </div>
  );
}

export type Situation = { element: string; phase: string; action: string };
const SITUATION_KEYS = ["element", "phase", "action"] as const;

/** 서버의 상황 메모(없으면 null)를 입력 칸 값으로 바꾼다. */
export function situationOf(
  value: Partial<Situation> | null | undefined,
): Situation {
  return {
    element: value?.element ?? "",
    phase: value?.phase ?? "",
    action: value?.action ?? "",
  };
}
export const isEmptySituation = (value: Partial<Situation> | null) =>
  SITUATION_KEYS.every((key) => !(value?.[key] ?? "").trim());
export const sameSituation = (a: Situation, b: Situation) =>
  SITUATION_KEYS.every((key) => a[key].trim() === b[key].trim());
export const situationSummary = (value: Situation) =>
  SITUATION_KEYS.map((key) => value[key].trim())
    .filter(Boolean)
    .join(" · ");

export function SituationHelper({
  open,
  value,
  dirty,
  error,
  onToggle,
  onChange,
  onSave,
}: {
  open: boolean;
  value: Situation;
  dirty: boolean;
  error: string;
  onToggle: () => void;
  onChange: (value: Situation) => void;
  onSave: () => void;
}) {
  const fields = [
    ["element", "관련 카드·요소", "예: 암살자, 백작 부인"],
    ["phase", "현재 단계", "예: 상대 차례, 저지 선언 직후"],
    ["action", "하려는 행동", "예: 저지에 도전하고 싶어요"],
  ] as const;
  const filled = fields.filter(([key]) => value[key].trim()).length;
  return (
    <div className="mb-2">
      <button
        type="button"
        className="chip"
        aria-expanded={open}
        aria-controls="situation-fields"
        onClick={onToggle}
      >
        상황 메모 {filled ? `${filled}/3` : ""}
        <svg
          aria-hidden
          viewBox="0 0 16 16"
          className={`size-3.5 transition-transform ${open ? "rotate-180" : ""}`}
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
        >
          <path d="m4 6 4 4 4-4" />
        </svg>
      </button>
      {open && (
        <div id="situation-fields" className="mt-2">
          <div className="grid gap-2 sm:grid-cols-3">
            {fields.map(([key, label, placeholder]) => (
              <label key={key} className="text-xs font-semibold text-muted">
                {label}
                <input
                  className="mt-1 w-full"
                  maxLength={300}
                  placeholder={placeholder}
                  value={value[key]}
                  onChange={(e) =>
                    onChange({ ...value, [key]: e.target.value })
                  }
                />
              </label>
            ))}
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <button
              type="button"
              className="chip"
              disabled={!dirty}
              onClick={onSave}
            >
              {dirty ? "메모 저장" : "저장됨"}
            </button>
            <p className="text-xs text-muted">
              저장한 메모는 이 대화의 다음 질문에도 계속 적용돼요.
            </p>
          </div>
          {error && (
            <p
              role="alert"
              className="mt-1 text-xs font-semibold text-red-deep"
            >
              {error}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
