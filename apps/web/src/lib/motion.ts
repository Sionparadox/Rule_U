import { stagger, type Transition, type Variants } from "motion/react";

/** 모션 토큰. DESIGN.md의 motion 항목과 같은 값을 쓴다. UI 모션은 300ms를 넘기지 않는다. */
export const easeOut = [0.23, 1, 0.32, 1] as const;

export const quick: Transition = { duration: 0.22, ease: easeOut };
/** 나갈 때는 들어올 때보다 빠르게. */
export const exitQuick: Transition = { duration: 0.12, ease: easeOut };
/** 상태가 바뀌는 조작(모드 전환 등): 튀지 않는 스프링. */
export const settle: Transition = {
  type: "spring",
  duration: 0.32,
  bounce: 0.12,
};
/** 판정 토큰처럼 드물게 보는 순간에만 쓰는 통통 튀는 스프링. */
export const playful: Transition = {
  type: "spring",
  duration: 0.45,
  bounce: 0.45,
};

/** 목록: 자식이 40ms 간격으로 떠오른다. */
export const list: Variants = {
  hidden: {},
  shown: { transition: { delayChildren: stagger(0.04) } },
};
export const rise: Variants = {
  hidden: { opacity: 0, y: 12, scale: 0.98 },
  shown: { opacity: 1, y: 0, scale: 1, transition: quick },
};
