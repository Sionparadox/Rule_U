"use client";

import { useEffect, useState, type ReactNode } from "react";
import { motion, useDragControls } from "motion/react";
import { easeOut, settle } from "@/lib/motion";

/**
 * 모바일 바텀 시트: 머리(handle)를 아래로 끌면 닫힌다. 일정 거리를 넘기거나 빠르게 튕기면
 * 닫히고, 아니면 제자리로 돌아온다. 닫기 버튼은 그대로 두어 끌기의 대안이 된다.
 */
export function DragSheet({
  onDismiss,
  handle,
  children,
}: {
  onDismiss: () => void;
  handle: ReactNode;
  children: ReactNode;
}) {
  const controls = useDragControls();
  const [mobile, setMobile] = useState(false);
  const [leaving, setLeaving] = useState(false);
  useEffect(() => {
    const query = matchMedia("(max-width: 639px)");
    const update = () => setMobile(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return (
    <motion.div
      drag={mobile ? "y" : false}
      dragListener={false}
      dragControls={controls}
      dragConstraints={{ top: 0, bottom: 0 }}
      dragElastic={{ top: 0.04, bottom: 0.7 }}
      animate={{ y: leaving ? "100%" : 0 }}
      transition={leaving ? { duration: 0.2, ease: easeOut } : settle}
      onDragEnd={(_, info) => {
        if (info.offset.y > 120 || info.velocity.y > 500) setLeaving(true);
      }}
      onAnimationComplete={() => {
        if (!leaving) return;
        // 닫힌 뒤 제자리로 돌려 두어야 다음에 열 때 시트가 보인다.
        onDismiss();
        setLeaving(false);
      }}
    >
      <div
        className={`relative ${mobile ? "touch-none" : ""}`}
        onPointerDown={(e) => {
          if (!mobile || (e.target as HTMLElement).closest("button")) return;
          controls.start(e);
        }}
      >
        {mobile && (
          <span
            aria-hidden
            className="absolute top-2 left-1/2 z-10 h-1.5 w-10 -translate-x-1/2 rounded-full bg-surface/80"
          />
        )}
        {handle}
      </div>
      {children}
    </motion.div>
  );
}
