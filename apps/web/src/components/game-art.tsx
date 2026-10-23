import type { Schema } from "@/lib/api";

/** 게임 타일 위쪽에 그리는 구성물 모티프. 실제 게임 이미지가 아니라 장르를 보여주는 그림이다. */
export type Motif =
  | "hex"
  | "gems"
  | "words"
  | "cards"
  | "meeples"
  | "dice"
  | "coins"
  | "cubes"
  | "timer"
  | "pawns";

// 이름과 분류(한국어·BGG 영문)를 함께 본다. 앞의 규칙이 먼저 맞으므로 흔한 분류(카드)는 뒤에 둔다.
const motifRules: [RegExp, Motif][] = [
  [
    /단어|파티|추리|코드네임|word|party|trivia|humor|deduction|bluff|mystery|spies/i,
    "words",
  ],
  [/실시간|스피드|순발력|real-time|dexterity|memory/i, "timer"],
  [/주사위|숫자|dice|number/i, "dice"],
  [
    /카탄|정착|타일|영토|문명|협상|territory|civilization|city building|negotiation|exploration/i,
    "hex",
  ],
  [/경제|경매|거래|투자|economic|industry|nautical|travel/i, "coins"],
  [/보석|스플렌더|자원|fantasy|mythology|renaissance|arabian/i, "gems"],
  [/레이스|경주|추상|abstract|racing|maze|sports|fighting|children/i, "pawns"],
  [/퍼즐|건설|생산|puzzle|environmental|science fiction|space/i, "cubes"],
  [
    /협력|가족|일꾼|배치|농장|동물|farming|animals|medieval|adventure|ancient/i,
    "meeples",
  ],
  [/카드|덱|card/i, "cards"],
];
// 장르를 특정하지 않는 모티프만 남겨, 맞지 않는 게임에 육각 타일 같은 그림이 붙지 않게 한다.
const fallback: Motif[] = ["dice", "meeples", "cards", "pawns", "cubes"];

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

type CubeColor = "red" | "blue" | "green";
// 클래스 이름을 문자열 조합으로 만들면 Tailwind가 찾지 못하므로 그대로 적어 둔다.
const cubeFace: Record<CubeColor, [string, string]> = {
  red: ["fill-red", "fill-red-deep"],
  blue: ["fill-blue", "fill-blue-deep"],
  green: ["fill-green", "fill-green-deep"],
};

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
          [44, 36, "fill-red"],
          [80, 30, "fill-surface"],
          [116, 36, "fill-green"],
          [60, 70, "fill-yellow"],
          [100, 70, "fill-blue"],
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
          const x = 25 + (i % 3) * 38;
          const y = 11 + Math.floor(i / 3) * 28;
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
          // 부채꼴로 펼친 묶음의 위아래 중심이 그림 중앙에 오도록 살짝 내린다.
          <g key={angle} transform={`translate(0 3) rotate(${angle} 80 96)`}>
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
        // 양옆 말을 먼저 그리고 가운데 큰 말을 위에 겹친다 (말 하나의 중심은 15, 15.5).
        [
          [14, 29.2, "fill-surface", 1.6],
          [98, 29.2, "fill-red", 1.6],
          [48.5, 17.5, "fill-yellow", 2.1],
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
        <g transform="translate(-1 -1)">
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
        </g>
      )}
      {motif === "coins" &&
        [
          [56, 59, "fill-yellow"],
          [104, 59, "fill-yellow"],
          [80, 41, "fill-surface"],
        ].map(([x, y, fill]) => (
          <g key={`${x}-${y}`}>
            <circle
              cx={x as number}
              cy={y as number}
              r="22"
              className={`${fill} ${piece}`}
            />
            <circle
              cx={x as number}
              cy={y as number}
              r="14"
              className={`fill-none ${piece} [stroke-width:2]`}
            />
            <path
              d={`M${x} ${(y as number) - 7}v14`}
              className="stroke-ink [stroke-linecap:round] [stroke-width:3]"
            />
          </g>
        ))}
      {motif === "cubes" &&
        // 아래 두 개 위에 하나를 얹은 나무 큐브 더미. 윗면은 밝게, 오른쪽 면은 진하게 칠한다.
        [
          [60, 60, "red"],
          [100, 60, "blue"],
          [80, 38, "green"],
        ].map(([x, y, color]) => {
          const cx = x as number;
          const cy = y as number;
          return (
            <g key={color}>
              <path
                d={`M${cx - 20} ${cy - 10}L${cx} ${cy}V${cy + 22}L${cx - 20} ${cy + 12}Z`}
                className={`${cubeFace[color as CubeColor][0]} ${piece}`}
              />
              <path
                d={`M${cx} ${cy}L${cx + 20} ${cy - 10}V${cy + 12}L${cx} ${cy + 22}Z`}
                className={`${cubeFace[color as CubeColor][1]} ${piece}`}
              />
              <path
                d={`M${cx} ${cy - 20}L${cx + 20} ${cy - 10}L${cx} ${cy}L${cx - 20} ${cy - 10}Z`}
                className={`fill-surface ${piece}`}
              />
            </g>
          );
        })}
      {motif === "timer" && (
        <>
          <path
            d="M62 22h36c0 16-12 22-12 28s12 12 12 28H62c0-16 12-22 12-28s-12-12-12-28Z"
            className={`fill-surface ${piece}`}
          />
          <path
            d="M67 28h26c-1 7-7 11-13 15-6-4-12-8-13-15Z"
            className="fill-yellow"
          />
          <path
            d="M66 76c1-9 8-13 14-15 6 2 13 6 14 15Z"
            className="fill-yellow"
          />
          <path
            d="M80 46v14"
            className="stroke-yellow-deep [stroke-linecap:round] [stroke-width:2.5]"
          />
          {[14, 78].map((y) => (
            <rect
              key={y}
              x="54"
              y={y}
              width="52"
              height="8"
              rx="4"
              className={`fill-blue ${piece}`}
            />
          ))}
        </>
      )}
      {motif === "pawns" &&
        // 양옆 말을 먼저 그리고 가운데 큰 말을 위에 겹친다. 말의 원점은 받침 밑면 가운데다.
        [
          [44, 80, 1, "fill-green"],
          [116, 80, 1, "fill-blue"],
          [80, 80.5, 1.3, "fill-surface"],
        ].map(([x, y, scale, fill]) => (
          <g
            key={x as number}
            transform={`translate(${x} ${y}) scale(${scale})`}
            className={`${fill} stroke-ink [stroke-linejoin:round] [stroke-width:2]`}
          >
            <path d="M-6 -29c0 8-8 16-8 22h28c0-6-8-14-8-22Z" />
            <circle cy="-37" r="9" />
            <rect x="-18" y="-8" width="36" height="8" rx="3" />
          </g>
        ))}
    </svg>
  );
}
