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
import { Dice } from "@/components/game-art";
import { useStore } from "@/lib/store";
import { api, type Schema } from "@/lib/api";

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
      <main
        className={`app-shell mx-auto px-4 pb-6 sm:px-7 ${view === "games" ? "max-w-[1040px]" : "max-w-[1160px]"}`}
      >
        <header className="flex h-20 items-center justify-between gap-3 sm:h-24">
          <button
            aria-label="Rule_U 게임 선택으로"
            onClick={() => useStore.setState({ view: "games" })}
            className="flex min-h-11 items-center gap-2 text-xl font-black tracking-tight"
          >
            <span className="flex size-10 rotate-[-8deg] items-center justify-center rounded-[13px] bg-felt text-2xl text-white shadow-[0_3px_0_#087b6d]">
              <Dice value={4} />
            </span>
            Rule<span className="-ml-2 text-felt">_U</span>
          </button>
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1.5 text-[11px] text-ink/60">
              <span
                className={`size-1.5 rounded-full ${connected ? "bg-felt" : "bg-token"}`}
              />
              {connected ? "서비스 연결됨" : "서비스 연결 대기"}
            </span>
            <span
              aria-hidden
              className="flex size-9 items-center justify-center rounded-full border-2 border-white bg-[#ffdf96] text-lg text-[#796024]"
            >
              ✦
            </span>
          </div>
        </header>
        {!hydrated ? (
          <div
            role="status"
            className="flex min-h-72 items-center justify-center gap-3 text-sm text-felt"
          >
            <span className="spinner" aria-hidden />
            게임을 준비하고 있어요…
          </div>
        ) : (
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={view}
              initial={{ opacity: 0, y: reduced ? 0 : 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: reduced ? 0 : 0.16 }}
            >
              {view === "games" ? (
                <GamePicker />
              ) : (
                <div className="mx-auto max-w-[760px]">
                  <Chat />
                  {sourcesOpen && source && (
                    <SourceModal key={source.id} source={source} />
                  )}
                </div>
              )}
            </motion.div>
          </AnimatePresence>
        )}
        {view === "games" && (
          <footer className="mt-9 pb-2 text-center text-xs text-ink/45">
            규칙은 가볍게, 플레이는 즐겁게.
          </footer>
        )}
      </main>
    </MotionConfig>
  );
}
