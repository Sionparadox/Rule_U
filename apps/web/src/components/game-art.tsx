import type { Schema } from "@/lib/api";

/** 게임 타일 위쪽에 그리는 구성물 모티프. 실제 게임 이미지가 아니라 장르를 보여주는 그림이다. */
export type Motif = "hex" | "gems" | "words" | "cards" | "meeples" | "dice";

const motifRules: [RegExp, Motif][] = [
  [/카탄|정착|타일|영토|문명|협상/, "hex"],
  [/보석|스플렌더|경제|자원/, "gems"],
  [/단어|파티|추리|코드네임/, "words"],
  [/카드|덱/, "cards"],
  [/협력|가족|일꾼|배치/, "meeples"],
];
// 장르를 특정하지 않는 모티프만 남겨, 맞지 않는 게임에 육각 타일 같은 그림이 붙지 않게 한다.
const fallback: Motif[] = ["dice", "meeples", "cards"];

const hash = (text: string) =>
  [...text].reduce((sum, ch) => (sum * 31 + ch.charCodeAt(0)) >>> 0, 7);

export function motifFor(
  game: Pick<Schema["GameOut"], "id" | "name_ko" | "categories">,
) {
  const text = [game.name_ko, ...(game.categories ?? [])].join(" ");
  return (
    motifRules.find(([pattern]) => pattern.test(text))?.[1] ??
    fallback[hash(game.id) % fallback.length]
  );
}

/** 말 색 네 가지를 돌려 쓴다. 목록 순서로 고르면 이웃한 타일의 색이 겹치지 않는다. */
export const tileColors = [
  "bg-blue",
  "bg-red",
  "bg-green",
  "bg-yellow",
] as const;
export const tileColor = (index: number) =>
  tileColors[index % tileColors.length];

const piece = "stroke-ink [stroke-width:2.5] [stroke-linejoin:round]";

function hexPath(cx: number, cy: number, r: number) {
  const points = Array.from({ length: 6 }, (_, i) => {
    const a = (Math.PI / 3) * i + Math.PI / 6;
    return `${(cx + r * Math.cos(a)).toFixed(1)},${(cy + r * Math.sin(a)).toFixed(1)}`;
  });
  return `M${points.join("L")}Z`;
}

const meeple =
  "M15 2a6 6 0 0 1 6 6c0 1.6-.6 3-1.7 4l8.2 3.6c2.4 1 2.2 4.4-.4 4.8l-4.6.7 3.9 7.9H18.6L15 22.6 11.4 29H3.6l3.9-7.9-4.6-.7c-2.6-.4-2.8-3.8-.4-4.8L10.7 12A6 6 0 0 1 15 2Z";

export function MeeplePath({ className }: { className?: string }) {
  return <path d={meeple} className={className} />;
}

export function GameArt({ motif }: { motif: Motif }) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 160 100"
      className="h-full w-full"
      preserveAspectRatio="xMidYMid meet"
    >
      {motif === "hex" &&
        [
          [80, 50, "fill-surface"],
          [51, 50, "fill-yellow"],
          [109, 50, "fill-green"],
          [65.5, 25, "fill-surface"],
          [94.5, 25, "fill-red"],
          [65.5, 75, "fill-blue"],
          [94.5, 75, "fill-surface"],
        ].map(([x, y, fill]) => (
          <path
            key={`${x}-${y}`}
            d={hexPath(x as number, y as number, 16)}
            className={`${fill} ${piece}`}
          />
        ))}
      {motif === "gems" &&
        [
          [44, 34, "fill-red"],
          [80, 28, "fill-surface"],
          [116, 34, "fill-green"],
          [60, 68, "fill-yellow"],
          [100, 68, "fill-blue"],
        ].map(([x, y, fill]) => (
          <g key={`${x}-${y}`}>
            <circle
              cx={x as number}
              cy={y as number}
              r="15"
              className={`${fill} ${piece}`}
            />
            <path
              d={`M${x} ${(y as number) - 7}l6 6-6 8-6-8Z`}
              className={`fill-surface ${piece} [stroke-width:2]`}
            />
          </g>
        ))}
      {motif === "words" &&
        Array.from({ length: 9 }, (_, i) => {
          const x = 24 + (i % 3) * 38;
          const y = 10 + Math.floor(i / 3) * 28;
          const fill =
            i === 1
              ? "fill-red"
              : i === 5
                ? "fill-blue"
                : i === 6
                  ? "fill-yellow"
                  : "fill-surface";
          return (
            <g key={i}>
              <rect
                x={x}
                y={y}
                width="34"
                height="22"
                rx="5"
                className={`${fill} ${piece}`}
              />
              <path
                d={`M${x + 8} ${y + 11}h18`}
                className="stroke-ink [stroke-linecap:round] [stroke-width:2.5]"
              />
            </g>
          );
        })}
      {motif === "cards" &&
        [-16, 0, 16].map((angle, i) => (
          <g key={angle} transform={`rotate(${angle} 80 96)`}>
            <rect
              x="60"
              y="16"
              width="40"
              height="58"
              rx="7"
              className={`${i === 1 ? "fill-surface" : i === 0 ? "fill-yellow" : "fill-red"} ${piece}`}
            />
            <path
              d="M80 36l7 9-7 9-7-9Z"
              className={`${i === 1 ? "fill-blue" : "fill-surface"} ${piece} [stroke-width:2]`}
            />
          </g>
        ))}
      {motif === "meeples" &&
        [
          [30, 26, "fill-surface", 1.7],
          [72, 18, "fill-yellow", 2.1],
          [114, 30, "fill-red", 1.6],
        ].map(([x, y, fill, scale]) => (
          <g
            key={x as number}
            transform={`translate(${x} ${y}) scale(${scale})`}
          >
            <path
              d={meeple}
              className={`${fill} stroke-ink [stroke-linejoin:round] [stroke-width:1.4]`}
            />
          </g>
        ))}
      {motif === "dice" && (
        <>
          <g transform="rotate(-12 58 52)">
            <rect
              x="34"
              y="28"
              width="48"
              height="48"
              rx="10"
              className={`fill-surface ${piece}`}
            />
            {[
              [46, 40],
              [70, 40],
              [58, 52],
              [46, 64],
              [70, 64],
            ].map(([x, y]) => (
              <circle
                key={`${x}-${y}`}
                cx={x}
                cy={y}
                r="4.5"
                className="fill-ink"
              />
            ))}
          </g>
          <g transform="rotate(14 106 50)">
            <rect
              x="84"
              y="26"
              width="44"
              height="44"
              rx="10"
              className={`fill-yellow ${piece}`}
            />
            {[
              [96, 38],
              [116, 58],
            ].map(([x, y]) => (
              <circle
                key={`${x}-${y}`}
                cx={x}
                cy={y}
                r="4.5"
                className="fill-ink"
              />
            ))}
          </g>
        </>
      )}
    </svg>
  );
}
