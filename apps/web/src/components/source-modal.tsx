"use client";

import { useEffect, useRef, useState } from "react";
import { api, type Schema } from "@/lib/api";
import { useStore } from "@/lib/store";

export function SourceModal({ source }: { source: Schema["SourceOut"] }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [detail, setDetail] = useState(source);
  const [busy, setBusy] = useState(!source.explanation);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const element = dialog.current;
    element?.showModal();
    return () => element?.close();
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
  return (
    <dialog
      ref={dialog}
      aria-labelledby="source-title"
      className="game-dialog w-[calc(100%-2rem)] max-w-xl rounded-[28px] border-0 bg-white p-0 text-ink shadow-xl backdrop:bg-[#103c36]/45"
      onClose={() => useStore.setState({ sourcesOpen: false })}
      onClick={(e) => {
        if (e.target === e.currentTarget) dialog.current?.close();
      }}
    >
      <div className="p-5 sm:p-7" data-testid="source-body">
        <div className="flex items-center justify-between gap-4">
          <span className="rounded-full bg-[#e5f5ef] px-3 py-1.5 text-xs font-bold text-felt">
            답변의 출처 {detail.number}
          </span>
          <button
            autoFocus
            className="btn size-11 rounded-full p-0 text-xl"
            aria-label="출처 설명 닫기"
            onClick={() => dialog.current?.close()}
          >
            ×
          </button>
        </div>
        <h2
          id="source-title"
          className="mt-4 text-xl font-extrabold sm:text-2xl"
        >
          왜 이렇게 답변했나요?
        </h2>
        <div className="mt-5 rounded-2xl border border-line bg-[#f5faf8] p-4">
          <p className="mb-2 text-xs font-semibold text-felt">
            {detail.source_review === "official_verified"
              ? "공식 출처 확인됨"
              : "공식 출처 확인이 필요한 자료"}
          </p>
          <h3 className="font-bold">{detail.title}</h3>
          <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-ink/65">
            <span>{detail.edition}</span>
            <span>{detail.language || "언어 미등록"}</span>
            <span>
              {detail.page_start
                ? `${detail.page_start}${detail.page_end && detail.page_end !== detail.page_start ? `–${detail.page_end}` : ""}페이지`
                : "페이지 정보 없음"}
            </span>
          </div>
        </div>
        {busy ? (
          <div role="status" className="mt-6 rounded-2xl bg-table p-5">
            <p className="mb-4 flex items-center gap-2 text-sm font-semibold text-felt">
              <span className="spinner" aria-hidden />
              규칙과 답변의 연결을 정리하고 있어요
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
              className="btn mt-3"
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
          <div className="mt-6 space-y-6">
            <section aria-labelledby="rule-summary">
              <h3
                id="rule-summary"
                className="mb-2 text-sm font-extrabold text-felt"
              >
                룰북의 관련 규칙
              </h3>
              <p className="text-[15px] leading-7 whitespace-pre-wrap break-words">
                {detail.explanation.rule_summary}
              </p>
            </section>
            <section
              className="rounded-2xl border-l-4 border-[#ffc76e] bg-[#fff8e9] p-4"
              aria-labelledby="rule-application"
            >
              <h3
                id="rule-application"
                className="mb-2 text-sm font-extrabold text-[#79531d]"
              >
                이 답변에 적용한 이유
              </h3>
              <p className="text-[15px] leading-7 whitespace-pre-wrap break-words">
                {detail.explanation.application}
              </p>
            </section>
            <p className="text-xs leading-5 text-ink/55">
              룰북의 해당 부분을 이해하기 쉽게 풀어 쓴 설명이에요. 정확한 표현은
              원문에서도 확인할 수 있어요.
            </p>
          </div>
        )}
        <div className="mt-6 flex flex-wrap gap-2 border-t border-line pt-4">
          {/^https?:\/\//i.test(detail.url) && (
            <a
              className="btn"
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
      </div>
    </dialog>
  );
}
