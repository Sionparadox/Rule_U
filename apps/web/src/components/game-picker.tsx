"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { api, errorText, type Schema } from "@/lib/api";
import { useStore } from "@/lib/store";
import { GameArt, gameVariant, cardColors } from "./game-art";

export function GamePicker() {
  const s = useStore();
  const reduced = useReducedMotion();
  const [query, setQuery] = useState("");
  const [semantic, setSemantic] = useState(false);
  const [players, setPlayers] = useState("");
  const [minutes, setMinutes] = useState("");
  const [category, setCategory] = useState("");
  const [categories, setCategories] = useState<string[]>([]);
  const [result, setResult] = useState<Schema["GameList"] | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const ticket = useRef(0);
  const form = useRef<HTMLFormElement>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      api<Schema["GameList"]>("/games", undefined, controller.signal),
      api<string[]>("/game-categories", undefined, controller.signal),
    ])
      .then(([games, genres]) => {
        setResult(games);
        setCategories(genres);
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(errorText(e));
      })
      .finally(() => {
        if (!controller.signal.aborted) setBusy(false);
      });
    return () => controller.abort();
  }, []);
  async function search(page = 1) {
    if (!form.current?.reportValidity()) return;
    const current = ++ticket.current;
    setBusy(true);
    setError("");
    const body = {
      query,
      players: players ? Number(players) : undefined,
      max_minutes: minutes ? Number(minutes) : undefined,
      category,
      page,
      page_size: 12,
    };
    const params = new URLSearchParams(
      Object.entries(body)
        .filter(([, v]) => v !== undefined)
        .map(([k, v]) => [k, String(v)]),
    );
    try {
      const data = semantic
        ? await api<Schema["GameList"]>("/games/search", body)
        : await api<Schema["GameList"]>(`/games?${params}`);
      if (current === ticket.current) setResult(data);
    } catch (e) {
      if (current === ticket.current) setError(errorText(e));
    } finally {
      if (current === ticket.current) setBusy(false);
    }
  }
  async function choose(id: string) {
    await s.selectGame(id);
    const state = useStore.getState();
    if (state.detail?.id === id && !state.error) dialog.current?.showModal();
  }
  return (
    <section aria-label="게임 탐색">
      <div className="mb-7 flex items-center justify-between gap-3 sm:mb-9">
        <div>
          <p className="mb-2 text-sm font-semibold text-felt">
            반가워요, 플레이어!
          </p>
          <h1 className="text-[28px] leading-tight font-extrabold tracking-tight sm:text-4xl">
            어떤 게임을 할까요?
          </h1>
          <p className="mt-3 text-sm leading-6 text-ink/65">
            게임을 고르면, 규칙 이야기가 시작돼요.
          </p>
        </div>
        <div aria-hidden className="hidden w-44 shrink-0 rotate-6 sm:block">
          <GameArt variant={5} />
        </div>
      </div>
      {s.conversation && (
        <button
          className="mb-5 flex w-full items-center justify-between gap-3 rounded-2xl border border-white bg-white/80 p-4 text-left shadow-[0_3px_0_#d3eae4]"
          onClick={() => useStore.setState({ view: "chat" })}
        >
          <span>
            <span className="block text-xs text-ink/60">
              지난 플레이를 이어갈까요?
            </span>
            <strong className="mt-1 block text-sm">
              {s.chatDetail?.name_ko ?? "저장된 게임"}
            </strong>
          </span>
          <span className="shrink-0 rounded-full bg-[#fff0c9] px-3 py-2 text-xs font-bold">
            이전 대화 이어하기 <span aria-hidden>↗</span>
          </span>
        </button>
      )}
      <form
        ref={form}
        onSubmit={(e) => {
          e.preventDefault();
          void search();
        }}
        className="mb-7"
      >
        <div className="flex items-center gap-2 rounded-2xl border-2 border-white bg-white p-2 shadow-[0_4px_0_#d3eae4]">
          <svg
            aria-hidden
            viewBox="0 0 24 24"
            className="ml-2 size-5 shrink-0 text-felt"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <circle cx="10.5" cy="10.5" r="6.5" />
            <path d="m16 16 5 5" />
          </svg>
          <label className="min-w-0 flex-1">
            <span className="sr-only">
              {semantic ? "자연어 조건" : "게임 이름"}
            </span>
            <input
              className="w-full border-0 bg-transparent px-1 shadow-none"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              maxLength={1000}
              placeholder={
                semantic ? "4명이 함께 할 게임" : "플레이할 게임을 검색하세요"
              }
            />
          </label>
          <button
            aria-label="게임 찾기"
            className="btn-primary shrink-0 px-4"
            disabled={busy}
          >
            {busy ? <span className="spinner" aria-hidden /> : "검색"}
          </button>
        </div>
        <details className="mt-4 rounded-2xl bg-white/65 px-4 open:pb-4">
          <summary className="flex min-h-11 cursor-pointer items-center justify-between text-xs font-semibold">
            인원·시간으로 더 찾아보기 <span aria-hidden>＋</span>
          </summary>
          <div className="grid grid-cols-2 gap-3 pt-2 sm:grid-cols-3">
            <label className="label">
              플레이 인원
              <input
                type="number"
                min={1}
                max={100}
                value={players}
                onChange={(e) => setPlayers(e.target.value)}
                placeholder="제한 없음"
              />
            </label>
            <label className="label">
              최대 시간 (분)
              <input
                type="number"
                min={1}
                max={1440}
                value={minutes}
                onChange={(e) => setMinutes(e.target.value)}
                placeholder="제한 없음"
              />
            </label>
            <label className="label col-span-2 sm:col-span-1">
              장르
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
              >
                <option value="">모든 장르</option>
                {categories.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </label>
          </div>
          <label className="mt-2 flex min-h-11 items-center gap-2 text-sm">
            <input
              type="checkbox"
              className="size-4 accent-felt"
              checked={semantic}
              onChange={(e) => setSemantic(e.target.checked)}
            />
            자연어로 찾기
          </label>
        </details>
      </form>
      {(error || s.error) && (
        <p
          role="alert"
          className="mb-4 rounded-xl bg-white p-3 text-sm text-red-800"
        >
          {error || s.error}
        </p>
      )}
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-extrabold">게임 선택</h2>
        <span className="text-xs font-medium text-ink/60">
          {result ? `${result.total}개의 게임` : "게임을 불러오는 중"}
        </span>
      </div>
      <div
        className="grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-3 lg:grid-cols-4"
        aria-busy={busy}
      >
        {busy
          ? Array.from({ length: 6 }, (_, i) => (
              <div
                key={i}
                aria-hidden
                className="h-48 animate-pulse rounded-[22px] bg-white/80 motion-reduce:animate-none"
              >
                <div className="m-4 h-4 w-20 rounded bg-line" />
                <div className="mx-4 h-3 w-12 rounded bg-line" />
                <div className="m-4 mt-8 h-16 rounded-xl bg-line/50" />
              </div>
            ))
          : result?.items.map((g) => {
              const variant = gameVariant(g.id);
              return (
                <motion.button
                  whileTap={reduced ? undefined : { scale: 0.97 }}
                  key={g.id}
                  aria-label={`${g.name_ko} 선택`}
                  disabled={s.loading}
                  onClick={() => void choose(g.id)}
                  className="game-card group relative flex min-h-[190px] flex-col overflow-hidden rounded-[22px] border-2 border-white/80 p-4 text-left sm:min-h-[218px]"
                  style={{ backgroundColor: cardColors[variant] }}
                >
                  <strong className="z-10 pr-3 text-[15px] leading-5 font-extrabold break-keep sm:text-base">
                    {g.name_ko}
                  </strong>
                  <span className="mt-1.5 text-[11px] font-medium text-ink/70">
                    {g.min_players}–{g.max_players}명{" "}
                    <span className="px-1 opacity-40">|</span>{" "}
                    {g.max_minutes
                      ? `${g.min_minutes}–${g.max_minutes}분`
                      : "시간 미등록"}
                  </span>
                  <div className="pointer-events-none -mx-4 mt-auto h-28 translate-y-3 transition-transform group-hover:translate-y-1 motion-reduce:transition-none sm:h-32">
                    <GameArt variant={variant} />
                  </div>
                  <span
                    aria-hidden
                    className="absolute right-3 bottom-3 flex size-7 items-center justify-center rounded-full bg-white/85 text-lg font-bold text-felt"
                  >
                    ↗
                  </span>
                </motion.button>
              );
            })}
      </div>
      {!busy && result?.items.length === 0 && (
        <div className="rounded-3xl bg-white p-8 text-center">
          <p className="font-bold">조건에 맞는 게임이 없어요.</p>
          <p className="mt-2 text-sm text-ink/60">
            게임 이름이나 인원·시간 조건을 바꿔보세요.
          </p>
        </div>
      )}
      {result && result.total > result.page_size && (
        <nav
          aria-label="게임 페이지"
          className="mt-6 flex items-center justify-center gap-5"
        >
          <button
            className="btn"
            disabled={busy || result.page === 1}
            onClick={() => void search(result.page - 1)}
          >
            이전
          </button>
          <span className="text-sm font-semibold">
            {result.page} / {Math.ceil(result.total / result.page_size)}
          </span>
          <button
            className="btn"
            disabled={busy || result.page * result.page_size >= result.total}
            onClick={() => void search(result.page + 1)}
          >
            다음
          </button>
        </nav>
      )}
      <p className="mt-6 text-center text-[11px] text-ink/50">
        카드 그림은 게임 선택을 돕는 장식용 이미지예요.
      </p>
      <dialog
        ref={dialog}
        aria-labelledby="setup-title"
        className="game-dialog w-[calc(100%-2rem)] max-w-md rounded-[28px] border-0 bg-[#f5fcfa] p-0 text-ink shadow-xl backdrop:bg-[#103c36]/40"
        onClick={(e) => {
          if (e.target === e.currentTarget) dialog.current?.close();
        }}
      >
        {s.detail && (
          <div className="p-6">
            <div className="mb-4 flex items-center justify-between">
              <p className="text-xs font-bold text-felt">플레이 준비</p>
              <button
                autoFocus
                className="btn size-11 rounded-full p-0 text-xl"
                aria-label="판본 선택 닫기"
                onClick={() => dialog.current?.close()}
              >
                ×
              </button>
            </div>
            <div className="mx-auto mb-3 h-28 w-52">
              <GameArt variant={gameVariant(s.detail.id)} />
            </div>
            <h2
              id="setup-title"
              className="mb-2 text-center text-2xl font-extrabold"
            >
              {s.detail.name_ko}
            </h2>
            <p className="mb-6 text-center text-xs text-ink/60">
              {s.detail.rules_supported ? "규칙 지원" : "규칙 지원 확인 필요"} /{" "}
              {s.detail.source_review === "official_verified"
                ? "공식 출처 확인"
                : "출처 확인 필요"}
            </p>
            <label className="label">
              사용할 판본
              <select
                value={s.edition}
                disabled={s.loading}
                onChange={(e) =>
                  useStore.setState({ edition: e.target.value, expansions: [] })
                }
              >
                {s.detail.editions.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.label} ({e.language})
                  </option>
                ))}
              </select>
            </label>
            <fieldset className="mt-4">
              <legend className="text-xs font-semibold text-ink/65">
                함께 쓰는 확장
              </legend>
              {s.detail.expansions
                .filter((e) => e.edition_ids?.includes(s.edition))
                .map((e) => (
                  <label
                    key={e.id}
                    className="flex min-h-11 items-center gap-2 text-sm"
                  >
                    <input
                      type="checkbox"
                      className="accent-felt"
                      disabled={!e.supported || s.loading}
                      checked={s.expansions.includes(e.id)}
                      onChange={(event) =>
                        useStore.setState({
                          expansions: event.target.checked
                            ? [...s.expansions, e.id]
                            : s.expansions.filter((id) => id !== e.id),
                        })
                      }
                    />
                    {e.name}
                    {!e.supported && " (준비 중)"}
                  </label>
                ))}
              {!s.detail.expansions.some((e) =>
                e.edition_ids?.includes(s.edition),
              ) && (
                <p className="mt-2 text-sm text-ink/60">
                  기본판으로 진행합니다.
                </p>
              )}
            </fieldset>
            {s.error && (
              <p role="alert" className="mt-3 text-sm text-red-800">
                {s.error}
              </p>
            )}
            <button
              className="btn-play mt-6 w-full"
              disabled={!s.edition || s.loading}
              onClick={() => void s.start()}
            >
              {s.loading ? (
                <>
                  <span className="spinner" />
                  대화 준비 중…
                </>
              ) : (
                "이 게임으로 대화하기"
              )}
            </button>
          </div>
        )}
      </dialog>
    </section>
  );
}
