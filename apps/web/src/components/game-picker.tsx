"use client";

import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion, type Variants } from "motion/react";
import { api, errorText, type Schema } from "@/lib/api";
import { list, quick, rise, settle } from "@/lib/motion";
import { useStore } from "@/lib/store";
import { DragSheet } from "./drag-sheet";
import { GameArt, motifFor, tileColor } from "./game-art";

// 마우스를 올리면 그림 속 구성물이 살짝 떠오른다 (터치에서는 hover가 일어나지 않는다).
const artLift: Variants = {
  hidden: { y: 0 },
  shown: { y: 0 },
  hover: { y: -4, transition: settle },
};

const verified = (game: Pick<Schema["GameOut"], "source_review">) =>
  game.source_review === "official_verified";

function playMeta(game: Schema["GameOut"]) {
  const players =
    game.min_players === game.max_players
      ? `${game.min_players}명`
      : `${game.min_players}–${game.max_players}명`;
  const minutes = game.max_minutes
    ? game.min_minutes === game.max_minutes
      ? `${game.max_minutes}분`
      : `${game.min_minutes}–${game.max_minutes}분`
    : "시간 미등록";
  return `${players}, ${minutes}`;
}

function SourceBadge({ ok }: { ok: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1 text-xs font-semibold ${ok ? "text-green-text" : "text-muted"}`}
    >
      <svg
        aria-hidden
        viewBox="0 0 16 16"
        className="size-3.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.25"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        {ok ? <path d="m3.5 8.5 3 3 6-7" /> : <circle cx="8" cy="8" r="5.5" />}
      </svg>
      {ok ? "공식 출처 확인" : "출처 확인 필요"}
    </span>
  );
}

export function GamePicker() {
  const s = useStore();
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
  // 시트의 그림 띠는 로비 타일과 같은 색을 쓴다.
  const colorOf = (id: string) =>
    tileColor(Math.max(0, result?.items.findIndex((g) => g.id === id) ?? 0));
  const recent = s.chatDetail;
  return (
    <section aria-label="게임 탐색">
      <div className="pt-4 pb-6 sm:pt-8">
        <h1 className="font-game text-[32px] leading-tight sm:text-[40px]">
          어떤 게임을 할까요?
        </h1>
        <p className="mt-1.5 text-[15px] text-muted">
          게임을 고르면 규칙서 근거와 함께 판정해 드려요.
        </p>
      </div>
      {s.conversation && (
        <motion.div
          className="mb-6"
          initial={{ opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={settle}
        >
          <button
            className="chunky flex w-full items-center gap-4 rounded-3xl bg-blue p-3 pr-4 text-left text-white [--depth-color:var(--color-blue-deep)]"
            onClick={() => useStore.setState({ view: "chat" })}
          >
            <span className="flex size-20 shrink-0 items-center justify-center rounded-2xl bg-surface p-1.5">
              {recent && <GameArt motif={motifFor(recent)} />}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-xs font-semibold text-white/85">
                최근 대화
              </span>
              <span className="font-game mt-0.5 block truncate text-[22px]">
                {recent?.name_ko ?? "저장된 게임"}
              </span>
            </span>
            <span className="font-game shrink-0 rounded-full bg-yellow px-4 py-2.5 text-[15px] whitespace-nowrap text-ink shadow-[0_3px_0_var(--color-yellow-deep)]">
              이전 대화 이어하기
            </span>
          </button>
        </motion.div>
      )}
      <form
        ref={form}
        onSubmit={(e) => {
          e.preventDefault();
          void search();
        }}
        className="mb-8"
      >
        <div className="chunky flex items-center gap-2 rounded-full border-[1.5px] border-edge bg-surface p-1.5 pl-4 focus-within:border-blue">
          <svg
            aria-hidden
            viewBox="0 0 24 24"
            className="size-5 shrink-0 text-muted"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.25"
          >
            <circle cx="10.5" cy="10.5" r="6.5" />
            <path d="m16 16 5 5" />
          </svg>
          <label className="min-w-0 flex-1">
            <span className="sr-only">
              {semantic ? "자연어 조건" : "게임 이름"}
            </span>
            <input
              className="w-full border-0 bg-transparent px-1 focus-visible:outline-0"
              name="q"
              autoComplete="off"
              enterKeyHint="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              maxLength={1000}
              placeholder={
                semantic ? "4명이 함께 할 전략 게임…" : "게임 이름 검색…"
              }
            />
          </label>
          <button
            aria-label="게임 찾기"
            className="btn-primary min-h-11 shrink-0 rounded-full px-5 [--depth:3px]"
            disabled={busy}
          >
            {busy ? <span className="spinner" aria-hidden /> : "검색"}
          </button>
        </div>
        <details className="group mt-3">
          <summary className="inline-flex min-h-11 cursor-pointer items-center gap-1.5 rounded-full px-1 text-sm font-semibold text-muted">
            인원·시간으로 더 찾아보기
            <svg
              aria-hidden
              viewBox="0 0 16 16"
              fill="none"
              className="size-4 transition-transform duration-200 group-open:rotate-180"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="m4 6 4 4 4-4" />
            </svg>
          </summary>
          <div className="mt-2 rounded-3xl bg-surface p-4 shadow-[0_4px_0_var(--color-edge)]">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <label className="label">
                플레이 인원
                <input
                  type="number"
                  name="players"
                  inputMode="numeric"
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
                  name="max_minutes"
                  inputMode="numeric"
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
            <label className="mt-3 flex min-h-11 items-center gap-2 text-sm font-semibold">
              <input
                type="checkbox"
                className="size-5 accent-blue"
                checked={semantic}
                onChange={(e) => setSemantic(e.target.checked)}
              />
              자연어로 찾기
            </label>
          </div>
        </details>
      </form>
      <AnimatePresence>
        {(error || s.error) && (
          <motion.p
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, transition: { duration: 0.12 } }}
            transition={quick}
            role="alert"
            className="mb-4 rounded-2xl bg-red/15 p-4 text-sm font-semibold text-ink"
          >
            {error || s.error}
          </motion.p>
        )}
      </AnimatePresence>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="font-game text-2xl">게임 선택</h2>
        <motion.span
          key={result?.total ?? "loading"}
          initial={{ scale: 1.12 }}
          animate={{ scale: 1 }}
          transition={settle}
          className="rounded-full bg-surface px-3 py-1 text-sm font-semibold text-muted"
        >
          {result ? `${result.total}개의 게임` : "게임을 불러오는 중…"}
        </motion.span>
      </div>
      <motion.div
        key={busy ? "loading" : (result?.items.map((g) => g.id).join() ?? "")}
        variants={list}
        initial="hidden"
        animate="shown"
        className="grid grid-cols-2 gap-3 sm:grid-cols-3 sm:gap-4 lg:grid-cols-4"
        aria-busy={busy}
      >
        {busy
          ? Array.from({ length: 6 }, (_, i) => (
              <div
                key={i}
                aria-hidden
                className="overflow-hidden rounded-3xl bg-surface shadow-[0_4px_0_var(--color-edge)]"
              >
                <div className="h-28 bg-surface-soft" />
                <div className="space-y-2 p-3">
                  <div className="skeleton-line w-3/4" />
                  <div className="skeleton-line w-1/2" />
                </div>
              </div>
            ))
          : result?.items.map((g, i) => (
              <motion.div
                key={g.id}
                variants={rise}
                whileHover="hover"
                className="flex"
              >
                <button
                  aria-label={`${g.name_ko} 선택`}
                  disabled={s.loading}
                  onClick={() => void choose(g.id)}
                  className="chunky flex w-full flex-col overflow-hidden rounded-3xl border-[1.5px] border-edge bg-surface text-left"
                >
                  <span className={`block h-28 w-full p-2 ${tileColor(i)}`}>
                    <motion.span variants={artLift} className="block h-full">
                      <GameArt motif={motifFor(g)} />
                    </motion.span>
                  </span>
                  <span className="flex flex-1 flex-col p-3">
                    <strong className="font-game text-lg leading-snug break-keep">
                      {g.name_ko}
                    </strong>
                    <span className="mt-0.5 text-xs text-muted">
                      {playMeta(g)}
                    </span>
                    <span className="mt-auto pt-2">
                      <SourceBadge ok={verified(g)} />
                    </span>
                  </span>
                </button>
              </motion.div>
            ))}
      </motion.div>
      {!busy && result?.items.length === 0 && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={quick}
          className="rounded-3xl bg-surface p-8 text-center shadow-[0_4px_0_var(--color-edge)]"
        >
          <p className="font-game text-xl">조건에 맞는 게임이 없어요.</p>
          <p className="mt-2 text-sm text-muted">
            게임 이름이나 인원·시간 조건을 바꿔보세요.
          </p>
        </motion.div>
      )}
      {result && result.total > result.page_size && (
        <nav
          aria-label="게임 페이지"
          className="mt-8 flex items-center justify-center gap-4"
        >
          <button
            className="btn-soft"
            disabled={busy || result.page === 1}
            onClick={() => void search(result.page - 1)}
          >
            이전
          </button>
          <span className="font-game text-lg">
            {result.page} / {Math.ceil(result.total / result.page_size)}
          </span>
          <button
            className="btn-soft"
            disabled={busy || result.page * result.page_size >= result.total}
            onClick={() => void search(result.page + 1)}
          >
            다음
          </button>
        </nav>
      )}
      <dialog
        ref={dialog}
        aria-labelledby="setup-title"
        className="sheet w-[calc(100%-2rem)] max-w-md overflow-hidden overscroll-contain rounded-[28px] border-0 bg-surface p-0 text-ink shadow-sheet"
        onClick={(e) => {
          if (e.target === e.currentTarget) dialog.current?.close();
        }}
      >
        {s.detail && (
          <DragSheet
            onDismiss={() => dialog.current?.close()}
            handle={
              <div className={`relative h-36 p-4 ${colorOf(s.detail.id)}`}>
                <GameArt motif={motifFor(s.detail)} />
                <button
                  autoFocus
                  className="icon-round absolute top-3 right-3"
                  aria-label="판본 선택 닫기"
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
            <div className="p-5 sm:p-6">
              <h2
                id="setup-title"
                className="font-game text-[28px] leading-tight"
              >
                {s.detail.name_ko}
              </h2>
              <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
                <span className="text-sm text-muted">{playMeta(s.detail)}</span>
                <SourceBadge ok={verified(s.detail)} />
              </div>
              {s.detail.description && (
                <p className="mt-3 text-[15px] leading-6">
                  {s.detail.description}
                </p>
              )}
              <div className="mt-5 space-y-4">
                <label className="label">
                  사용할 판본
                  <select
                    value={s.edition}
                    disabled={s.loading}
                    onChange={(e) =>
                      useStore.setState({
                        edition: e.target.value,
                        expansions: [],
                      })
                    }
                  >
                    {s.detail.editions.map((e) => (
                      <option key={e.id} value={e.id}>
                        {e.label} ({e.language})
                      </option>
                    ))}
                  </select>
                </label>
                <fieldset>
                  <legend className="mb-2 text-sm font-semibold">
                    함께 쓰는 확장
                  </legend>
                  <div className="flex flex-wrap gap-2">
                    {s.detail.expansions
                      .filter((e) => e.edition_ids?.includes(s.edition))
                      .map((e) => (
                        <label
                          key={e.id}
                          className="flex min-h-11 items-center gap-2 rounded-2xl border-[1.5px] border-edge bg-surface px-3 text-sm font-semibold has-checked:border-blue has-checked:bg-blue/10 has-disabled:text-muted"
                        >
                          <input
                            type="checkbox"
                            className="size-4 accent-blue"
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
                          {!e.supported && (
                            <span className="text-xs font-medium">준비 중</span>
                          )}
                        </label>
                      ))}
                  </div>
                  {!s.detail.expansions.some((e) =>
                    e.edition_ids?.includes(s.edition),
                  ) && (
                    <p className="text-sm text-muted">기본판으로 진행합니다.</p>
                  )}
                </fieldset>
              </div>
              {s.error && (
                <p
                  role="alert"
                  className="mt-4 rounded-2xl bg-red/15 p-3 text-sm font-semibold"
                >
                  {s.error}
                </p>
              )}
              <button
                className="btn-play mt-6 w-full text-lg"
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
          </DragSheet>
        )}
      </dialog>
    </section>
  );
}
