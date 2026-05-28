/**
 * Cross-section of a single turbomachinery stage with the nine canonical
 * loss mechanisms labelled. Used in Chapter 5.
 *
 * Layout: a stator (left) and a rotor (right) on a single mean-radius
 * cross-section. Each loss mechanism is called out with a leader line.
 * The schematic deliberately keeps blade shapes generic — the same
 * mechanisms apply to axial and radial machines.
 */
export function LossMechanisms({
  className,
}: {
  className?: string;
}) {
  return (
    <svg
      viewBox="0 0 720 420"
      className={className}
      role="img"
      aria-label="Cross-section of a turbomachinery stage with each of the nine canonical loss mechanisms labelled."
    >
      <title>Loss mechanisms in a turbomachinery stage</title>

      {/* Hub and casing — the duct */}
      <g stroke="currentColor" strokeWidth="1.4" fill="none">
        <line x1="60" y1="90" x2="660" y2="90" />
        <line x1="60" y1="290" x2="660" y2="290" />
      </g>

      {/* Stator blade (left) */}
      <g>
        <path
          d="M 180 100 Q 240 130 260 160 Q 230 200 200 240 Q 160 220 150 180 Q 160 130 180 100 Z"
          fill="rgb(var(--surface-subtle))"
          stroke="currentColor"
          strokeWidth="1.4"
        />
        <text
          x="200"
          y="170"
          textAnchor="middle"
          fontSize="11"
          fontFamily="var(--font-mono)"
          fill="rgb(var(--text-muted))"
        >
          stator
        </text>
      </g>

      {/* Rotor blade (right) — drawn with a wake */}
      <g>
        <path
          d="M 420 100 Q 470 140 470 180 Q 460 220 430 260 Q 390 230 380 180 Q 390 140 420 100 Z"
          fill="rgb(var(--surface-subtle))"
          stroke="currentColor"
          strokeWidth="1.4"
        />
        <text
          x="425"
          y="180"
          textAnchor="middle"
          fontSize="11"
          fontFamily="var(--font-mono)"
          fill="rgb(var(--text-muted))"
        >
          rotor
        </text>
        {/* tip clearance gap */}
        <line
          x1="385"
          y1="92"
          x2="450"
          y2="92"
          stroke="rgb(var(--danger-default))"
          strokeWidth="2"
        />
        {/* wake */}
        <path
          d="M 450 250 Q 510 240 560 260 Q 520 270 470 280"
          fill="none"
          stroke="rgb(var(--text-muted))"
          strokeWidth="0.8"
          strokeDasharray="3 3"
        />
      </g>

      {/* Flow arrows */}
      <g
        stroke="rgb(var(--info-default))"
        strokeWidth="1.4"
        fill="rgb(var(--info-default))"
      >
        <path d="M 70 180 L 130 180" fill="none" />
        <polyline points="124 174, 130 180, 124 186" fill="none" />
        <path d="M 540 200 L 600 200" fill="none" />
        <polyline points="594 194, 600 200, 594 206" fill="none" />
      </g>

      {/* === Loss callouts === */}
      {/* 1. Incidence loss — blade leading edge */}
      <Callout
        x={180}
        y={75}
        label="1"
        text="Incidence"
        sub="flow hits LE at wrong angle"
        targetX={180}
        targetY={102}
      />

      {/* 2. Profile loss — blade surface */}
      <Callout
        x={140}
        y={205}
        label="2"
        text="Profile"
        sub="skin friction on blade"
        targetX={170}
        targetY={195}
      />

      {/* 3. Secondary flow — corner vortex */}
      <Callout
        x={300}
        y={310}
        label="3"
        text="Secondary"
        sub="corner / passage vortex"
        targetX={250}
        targetY={285}
      />

      {/* 4. Tip clearance */}
      <Callout
        x={470}
        y={45}
        label="4"
        text="Tip clearance"
        sub="leakage over unshrouded tip"
        targetX={420}
        targetY={92}
      />

      {/* 5. Trailing edge wake */}
      <Callout
        x={580}
        y={310}
        label="5"
        text="Trailing-edge wake"
        sub="mixing behind finite TE"
        targetX={510}
        targetY={263}
      />

      {/* 6. Disc friction */}
      <Callout
        x={620}
        y={170}
        label="6"
        text="Disc friction"
        sub="windage on rotor back face"
        targetX={530}
        targetY={170}
        rightAlign
      />

      {/* 7. Recirculation */}
      <Callout
        x={250}
        y={365}
        label="7"
        text="Recirculation"
        sub="re-entrained near-wall flow"
        targetX={205}
        targetY={290}
      />

      {/* 8. Mixing */}
      <Callout
        x={500}
        y={345}
        label="8"
        text="Mixing"
        sub="downstream stream-to-stream"
        targetX={510}
        targetY={290}
      />

      {/* 9. Shock loss */}
      <Callout
        x={50}
        y={395}
        label="9"
        text="Shock"
        sub="only above Mach 1"
        targetX={150}
        targetY={250}
      />
    </svg>
  );
}

function Callout({
  x,
  y,
  label,
  text,
  sub,
  targetX,
  targetY,
  rightAlign,
}: {
  x: number;
  y: number;
  label: string;
  text: string;
  sub: string;
  targetX: number;
  targetY: number;
  rightAlign?: boolean;
}) {
  return (
    <g>
      {/* leader line */}
      <line
        x1={x}
        y1={y}
        x2={targetX}
        y2={targetY}
        stroke="rgb(var(--border-default))"
        strokeWidth="0.8"
        strokeDasharray="2 2"
      />
      {/* number bubble */}
      <circle
        cx={x}
        cy={y}
        r="9"
        fill="rgb(var(--brand-default))"
        stroke="rgb(var(--brand-default))"
      />
      <text
        x={x}
        y={y + 4}
        textAnchor="middle"
        fontSize="11"
        fontFamily="var(--font-mono)"
        fontWeight="600"
        fill="rgb(var(--text-inverse))"
      >
        {label}
      </text>
      {/* label text */}
      <text
        x={x + (rightAlign ? -14 : 14)}
        y={y + 2}
        textAnchor={rightAlign ? "end" : "start"}
        fontSize="11"
        fontFamily="var(--font-sans)"
        fontWeight="500"
        fill="rgb(var(--text-default))"
      >
        {text}
      </text>
      <text
        x={x + (rightAlign ? -14 : 14)}
        y={y + 14}
        textAnchor={rightAlign ? "end" : "start"}
        fontSize="9"
        fontFamily="var(--font-sans)"
        fill="rgb(var(--text-muted))"
      >
        {sub}
      </text>
    </g>
  );
}
