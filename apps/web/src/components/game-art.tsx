export function Dice({ value = 5 }: { value?: number }) {
  const positions = [
    [4],
    [0, 8],
    [0, 4, 8],
    [0, 2, 6, 8],
    [0, 2, 4, 6, 8],
    [0, 2, 3, 5, 6, 8],
  ][value - 1];
  return (
    <svg
      aria-hidden
      viewBox="0 0 24 24"
      className="h-[1em] w-[1em]"
      fill="none"
    >
      <rect
        x="1.5"
        y="1.5"
        width="21"
        height="21"
        rx="6"
        stroke="currentColor"
        strokeWidth="1.7"
      />
      {positions.map((p) => (
        <circle
          key={p}
          cx={6 + (p % 3) * 6}
          cy={6 + Math.floor(p / 3) * 6}
          r="1.6"
          fill="currentColor"
        />
      ))}
    </svg>
  );
}

export function gameVariant(id: string) {
  return [...id].reduce((n, c) => n + c.charCodeAt(0), 0) % 6;
}
export const cardColors = [
  "#b9ead7",
  "#bce4f5",
  "#f8dcaf",
  "#d9d1f3",
  "#f5cbd0",
  "#bbe9e5",
];

// Decorative game pieces, not depictions of a game's actual components or box art.
export function GameArt({ variant = 0 }: { variant?: number }) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 240 130"
      className="h-full w-full"
      fill="none"
    >
      <ellipse cx="126" cy="118" rx="82" ry="9" fill="#163c38" opacity=".09" />
      {variant === 0 && (
        <g transform="translate(48 12) rotate(-8 72 50)">
          <rect width="148" height="101" rx="15" fill="#0f8776" />
          {Array.from({ length: 20 }, (_, i) => (
            <g key={i}>
              <circle
                cx={19 + (i % 5) * 27}
                cy={18 + Math.floor(i / 5) * 22}
                r="8"
                fill={
                  i % 4 === 0 ? "#ffcb76" : i % 3 === 0 ? "#f7fffc" : "#43bda4"
                }
              />
              <circle
                cx={17 + (i % 5) * 27}
                cy={16 + Math.floor(i / 5) * 22}
                r="3"
                fill="white"
                opacity=".3"
              />
            </g>
          ))}
        </g>
      )}
      {variant === 1 && (
        <g transform="translate(40 8)">
          <rect
            x="15"
            y="15"
            width="115"
            height="90"
            rx="13"
            fill="#fff"
            transform="rotate(-13 70 60)"
          />
          <rect
            x="65"
            y="2"
            width="95"
            height="112"
            rx="13"
            fill="#108d7d"
            transform="rotate(12 110 60)"
          />
          <path d="M112 27 137 56 112 85 87 56Z" fill="#ffd58a" />
          <circle cx="112" cy="56" r="9" fill="#fff4dc" />
          <circle cx="26" cy="50" r="8" fill="#ffb766" />
          <path d="m37 80 10-16 10 16Z" fill="#d5d0f0" />
        </g>
      )}
      {variant === 2 && (
        <g>
          <path d="M39 106 70 40h99l31 66Z" fill="#faf9e9" />
          <path
            d="M63 104 82 41m13 65 7-65m22 65-1-65m31 65-12-65m-93 45h138M59 65h117"
            stroke="#329a87"
            strokeWidth="10"
          />
          <ellipse
            cx="99"
            cy="107"
            rx="22"
            ry="6"
            fill="#114c43"
            opacity=".2"
          />
          <path d="m82 93 7-32-6-14 10-14h17l9 14-7 14 7 32Z" fill="#17715f" />
          <circle cx="101" cy="27" r="12" fill="#198975" />
          <rect x="78" y="91" width="46" height="13" rx="6" fill="#125849" />
          <circle cx="161" cy="76" r="17" fill="#ffbd6e" />
          <ellipse cx="157" cy="70" rx="6" ry="4" fill="#ffe2b5" />
        </g>
      )}
      {variant === 3 && (
        <g transform="translate(50 15) rotate(8 72 50)">
          <rect width="138" height="100" rx="16" fill="#fcfaff" />
          <path
            d="M46 12v76m46-76v76M12 33h114M12 67h114"
            stroke="#c9bce7"
            strokeWidth="3"
          />
          <path
            d="m17 12 14 14m0-14L17 26m88 49 14 14m0-14-14 14m-59-37 14 14m0-14L59 60"
            stroke="#188e80"
            strokeWidth="6"
            strokeLinecap="round"
          />
          <circle cx="69" cy="18" r="10" stroke="#eea65f" strokeWidth="6" />
          <circle cx="23" cy="82" r="10" stroke="#eea65f" strokeWidth="6" />
          <circle cx="115" cy="50" r="10" stroke="#eea65f" strokeWidth="6" />
        </g>
      )}
      {variant === 4 && (
        <g>
          <path d="m36 101 39-70 139 22-34 65Z" fill="#fff0e9" />
          <path
            d="m55 105 39-71m-10 76 37-71m-6 77 34-72m-2 76 30-70M54 70l140 23M65 50l140 23"
            stroke="#eba8a3"
            strokeWidth="10"
          />
          {[
            [85, 57],
            [130, 89],
            [165, 65],
          ].map(([x, y], i) => (
            <g key={i}>
              <ellipse cx={x} cy={y + 6} rx="19" ry="8" fill="#126a5b" />
              <ellipse cx={x} cy={y} rx="19" ry="8" fill="#1ca88e" />
              <ellipse
                cx={x}
                cy={y - 2}
                rx="12"
                ry="4"
                stroke="#6ad3b9"
                strokeWidth="2"
              />
            </g>
          ))}
          <ellipse cx="79" cy="99" rx="20" ry="9" fill="#ffbd6e" />
        </g>
      )}
      {variant === 5 && (
        <g>
          <rect
            x="48"
            y="30"
            width="79"
            height="79"
            rx="18"
            fill="#128f7b"
            transform="rotate(-14 87 69)"
          />
          <rect
            x="121"
            y="12"
            width="73"
            height="73"
            rx="17"
            fill="#fffdf2"
            transform="rotate(15 157 48)"
          />
          {[
            [69, 51],
            [103, 83],
            [86, 67],
          ].map(([x, y]) => (
            <circle key={x} cx={x} cy={y} r="6" fill="#fff7e5" />
          ))}
          {[
            [144, 34],
            [174, 43],
            [137, 62],
            [166, 71],
          ].map(([x, y]) => (
            <circle key={x} cx={x} cy={y} r="5.5" fill="#e4a24d" />
          ))}
          <circle cx="178" cy="108" r="12" fill="#f2b461" />
          <circle cx="35" cy="91" r="8" fill="#72cfb6" />
        </g>
      )}
    </svg>
  );
}
