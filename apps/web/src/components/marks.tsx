import { MeeplePath } from "./game-art";

/** 파랑 말 = Rule_U. 장식이므로 보조기기에는 숨긴다. */
export function BrandMark({ className = "size-8" }: { className?: string }) {
  return (
    <svg aria-hidden viewBox="-2 -1 34 34" className={className}>
      <MeeplePath className="fill-blue stroke-ink [stroke-linejoin:round] [stroke-width:2]" />
    </svg>
  );
}

/** 답변을 기다리는 동안 굴러가는 주사위 (.spinner.dice 가 굴린다). */
export function RollingDice() {
  return (
    <svg aria-hidden viewBox="0 0 36 36" className="spinner dice">
      <rect
        x="3"
        y="3"
        width="30"
        height="30"
        rx="8"
        className="fill-surface stroke-ink [stroke-width:2.5]"
      />
      {[
        [11, 11],
        [25, 11],
        [18, 18],
        [11, 25],
        [25, 25],
      ].map(([x, y]) => (
        <circle key={`${x}-${y}`} cx={x} cy={y} r="3" className="fill-blue" />
      ))}
    </svg>
  );
}
