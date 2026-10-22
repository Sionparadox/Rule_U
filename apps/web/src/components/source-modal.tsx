"use client";

import { useEffect, useRef, useState } from "react";
import { motion } from "motion/react";
import { api, type Schema } from "@/lib/api";
import { quick } from "@/lib/motion";
import { DragSheet } from "./drag-sheet";
import { useStore } from "@/lib/store";

export function SourceModal({ source }: { source: Schema["SourceOut"] }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [detail, setDetail] = useState(source);
  const [busy, setBusy] = useState(!source.explanation);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    // 정리 함수에서 close()를 부르면 개발 모드의 effect 재실행 때
    // close 이벤트가 sourcesOpen을 꺼서 모달이 바로 닫힌다. 언마운트되면
    // dialog는 화면에서 함께 사라지므로 열기만 한다.
    const element = dialog.current;
    if (element && !element.open) element.showModal();
  }, []);
  useEffect(() => {
    if (source.explanation) return;
    const controller = new AbortController();
    api<Schema["SourceOut"]>(
      `/sources/${source.id}/explanation`,
      {},
      controller.signal,
      125000,
    )
      .then((value) => {
        if (!controller.signal.aborted) setDetail(value);
      })
      .catch(() => {
        if (!controller.signal.aborted) setError(true);
      })
      .finally(() => {
        if (!controller.signal.aborted) setBusy(false);
      });
    return () => controller.abort();
  }, [source.id, source.explanation, attempt]);
  const community = detail.source_type === "bgg_community";
  return (
    <dialog
      ref={dialog}
      aria-labelledby="source-title"
      className="sheet w-[calc(100%-2rem)] max-w-xl overflow-hidden overscroll-contain rounded-[28px] border-0 bg-surface p-0 text-ink shadow-sheet"
      onClose={() => useStore.setState({ sourcesOpen: false })}
      onClick={(e) => {
        if (e.target === e.currentTarget) dialog.current?.close();
      }}
    >
      <DragSheet
        onDismiss={() => dialog.current?.close()}
        handle={
          <div className="flex items-center justify-between gap-4 bg-blue px-5 py-3.5 text-white">
            <p className="font-game flex items-center gap-2.5 text-lg">
              <span className="flex size-9 items-center justify-center rounded-xl bg-surface text-xl text-blue">
                {detail.number}
              </span>
              답변의 출처
            </p>
            <button
              autoFocus
              className="icon-round [--depth-color:var(--color-blue-deep)]"
              aria-label="출처 설명 닫기"
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
        <div className="p-5 sm:p-6" data-testid="source-body">
          <h2 id="source-title" className="font-game text-[26px] leading-tight">
            왜 이렇게 답변했나요?
          </h2>
          <div className="mt-4 rounded-3xl bg-ground p-4">
            <p className="flex items-center gap-1.5 text-xs font-semibold text-muted">
              <span
                aria-hidden
                className={`size-2.5 rounded-full ${community ? "bg-yellow" : detail.source_review === "official_verified" ? "bg-green" : "bg-edge"}`}
              />
              {community
                ? "BGG 커뮤니티 토론 · 공식 룰북 아님"
                : detail.source_review === "official_verified"
                  ? "공식 출처 확인됨"
                  : "공식 출처 확인이 필요한 자료"}
            </p>
            <h3 className="font-game mt-1 text-xl">{detail.title}</h3>
            <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-sm text-muted">
              <span>{detail.edition}</span>
              <span>{detail.language || "언어 미등록"}</span>
              <span className="font-semibold text-ink">
                {detail.page_start
                  ? `${detail.page_start}${detail.page_end && detail.page_end !== detail.page_start ? `–${detail.page_end}` : ""}페이지`
                  : "페이지 정보 없음"}
              </span>
            </div>
          </div>
          {busy ? (
            <div role="status" className="mt-6">
              <p className="mb-4 flex items-center gap-2 text-sm font-semibold text-blue">
                <span className="spinner" aria-hidden />
                규칙과 답변의 연결을 정리하고 있어요…
              </p>
              <div aria-hidden className="space-y-3">
                <div className="skeleton-line w-full" />
                <div className="skeleton-line w-4/5" />
                <div className="skeleton-line w-3/5" />
              </div>
            </div>
          ) : error || !detail.explanation ? (
            <div role="alert" className="mt-6 text-sm leading-6">
              <p>
                이 출처의 설명을 불러오지 못했어요. 잠시 후 다시 시도하거나
                원문에서 해당 페이지를 확인해 주세요.
              </p>
              <button
                className="btn-soft mt-3"
                onClick={() => {
                  setBusy(true);
                  setError(false);
                  setAttempt((v) => v + 1);
                }}
              >
                설명 다시 불러오기
              </button>
            </div>
          ) : (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={quick}
              className="mt-6 space-y-5"
            >
              <section aria-labelledby="rule-summary">
                <h3 id="rule-summary" className="font-game mb-1 text-lg">
                  {community ? "토론에서 참고한 내용" : "룰북의 관련 규칙"}
                </h3>
                <p className="text-[15px] leading-7 break-words whitespace-pre-wrap">
                  {detail.explanation.rule_summary}
                </p>
              </section>
              <section
                className="rounded-3xl bg-yellow/30 p-4"
                aria-labelledby="rule-application"
              >
                <h3 id="rule-application" className="font-game mb-1 text-lg">
                  이 답변에 적용한 이유
                </h3>
                <p className="text-[15px] leading-7 break-words whitespace-pre-wrap">
                  {detail.explanation.application}
                </p>
              </section>
              <p className="text-xs leading-5 text-muted">
                {community
                  ? "일반 사용자들의 규칙 토론을 요약했어요. 판본과 확장에 따라 다를 수 있으니 공식 룰북도 확인해 주세요."
                  : "룰북의 해당 부분을 이해하기 쉽게 풀어 쓴 설명이에요. 정확한 표현은 원문에서도 확인할 수 있어요."}
              </p>
            </motion.div>
          )}
          {(/^https?:\/\//i.test(detail.url) || detail.original_available) && (
            <div className="mt-6 flex flex-wrap gap-3">
              {/^https?:\/\//i.test(detail.url) && (
                <a
                  className="btn-soft"
                  href={detail.url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  출처 웹사이트
                </a>
              )}
              {detail.original_available && (
                <a
                  className="btn-primary"
                  href={`/api/v1/documents/${encodeURIComponent(detail.document_id)}/original`}
                >
                  원문 다운로드
                </a>
              )}
            </div>
          )}
        </div>
      </DragSheet>
    </dialog>
  );
}
