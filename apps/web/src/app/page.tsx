"use client";

import { useEffect, useState } from "react";
import {
  AnimatePresence,
  motion,
  MotionConfig,
  useReducedMotion,
} from "motion/react";
import { GamePicker } from "@/components/game-picker";
import { Chat } from "@/components/conversation";
import { SourceModal } from "@/components/source-modal";
import { BrandMark, RollingDice } from "@/components/marks";
import { useStore } from "@/lib/store";
import { api, API_MOCK, type Schema } from "@/lib/api";

export default function Home() {
  const { hydrated, view, sourcesOpen, source } = useStore();
  const [connected, setConnected] = useState(false);
  const reduced = useReducedMotion();
  useEffect(() => {
    void useStore.getState().init();
    api<Schema["HealthOut"]>("/health")
      .then(() => setConnected(true))
      .catch(() => setConnected(false));
  }, []);
  return (
    <MotionConfig reducedMotion="user">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:rounded-2xl focus:bg-blue focus:px-4 focus:py-3 focus:text-white"
      >
        본문으로 건너뛰기
      </a>
      <main id="main" className="mx-auto max-w-[960px] px-4 pb-10 sm:px-6">
        <header className="flex h-16 items-center justify-between gap-3 sm:h-[72px]">
          <button
            aria-label="Rule_U 게임 선택으로"
            onClick={() => useStore.setState({ view: "games" })}
            className="font-game -ml-1 flex min-h-11 items-center gap-2 rounded-2xl px-1 text-2xl text-ink"
          >
            <BrandMark />
            <span translate="no">Rule_U</span>
          </button>
          <div className="flex items-center gap-2 text-xs font-semibold">
            {API_MOCK && (
              <span className="rounded-full bg-yellow px-3 py-1.5 text-ink">
                목 데이터
              </span>
            )}
            <span className="flex items-center gap-1.5 rounded-full bg-surface px-3 py-1.5 text-ink shadow-[0_2px_0_var(--color-edge)]">
              <span
                aria-hidden
                className={`size-2 rounded-full ${connected ? "bg-green" : "bg-edge"}`}
              />
              {connected ? "서비스 연결됨" : "서비스 연결 대기"}
            </span>
          </div>
        </header>
        {!hydrated ? (
          <div
            role="status"
            className="flex min-h-72 flex-col items-center justify-center gap-3 text-sm font-semibold text-muted"
          >
            <RollingDice />
            게임 목록을 불러오고 있어요…
          </div>
        ) : (
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={view}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: reduced ? 0 : 0.12 }}
            >
              {view === "games" ? (
                <GamePicker />
              ) : (
                <div className="mx-auto max-w-[720px]">
                  <Chat />
                  {sourcesOpen && source && (
                    <SourceModal key={source.id} source={source} />
                  )}
                </div>
              )}
            </motion.div>
          </AnimatePresence>
        )}
      </main>
    </MotionConfig>
  );
}
