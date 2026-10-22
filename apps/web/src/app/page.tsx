"use client";

import { useEffect, useState } from "react";
import {
  AnimatePresence,
  motion,
  MotionConfig,
  type Variants,
} from "motion/react";
import { GamePicker } from "@/components/game-picker";
import { Chat } from "@/components/conversation";
import { SourceModal } from "@/components/source-modal";
import { BrandMark, RollingDice } from "@/components/marks";
import { useStore } from "@/lib/store";
import { api, API_MOCK, type Schema } from "@/lib/api";
import { exitQuick, playful, quick } from "@/lib/motion";

type View = "games" | "chat";
// 대화는 오른쪽에서 들어오고, 로비로 돌아갈 때는 왼쪽에서 들어온다 (공간 방향을 일관되게).
const screens: Variants = {
  enter: (to: View) => ({ opacity: 0, x: to === "chat" ? 24 : -24 }),
  center: { opacity: 1, x: 0, transition: quick },
  leave: (to: View) => ({
    opacity: 0,
    x: to === "chat" ? -24 : 24,
    transition: exitQuick,
  }),
};

export default function Home() {
  const { hydrated, view, sourcesOpen, source } = useStore();
  const [connected, setConnected] = useState(false);
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
              <motion.span
                aria-hidden
                key={String(connected)}
                initial={{ scale: connected ? 1.8 : 1 }}
                animate={{ scale: 1 }}
                transition={playful}
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
          <AnimatePresence mode="wait" initial={false} custom={view}>
            <motion.div
              key={view}
              custom={view}
              variants={screens}
              initial="enter"
              animate="center"
              exit="leave"
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
