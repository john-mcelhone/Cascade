/**
 * Turbocharger cutaway — radial turbine wheel and centrifugal compressor
 * wheel sharing one shaft. Used in Chapter 1 to open with a concrete
 * machine.
 *
 * Conventions:
 *   - left side: hot exhaust gas drives the radial turbine wheel
 *   - right side: cold intake air is compressed by the centrifugal wheel
 *   - center: bearing housing + shaft
 *
 * Colors:
 *   - exhaust flow uses semantic-danger (hot)
 *   - intake flow uses semantic-info (cold)
 *   - structural elements use currentColor for dark-mode safety
 */
export function TurbochargerCutaway({
  className,
}: {
  className?: string;
}) {
  return (
    <svg
      viewBox="0 0 560 280"
      className={className}
      role="img"
      aria-label="Turbocharger cross-section: a radial turbine wheel on the exhaust side shares a shaft with a centrifugal compressor wheel on the intake side."
    >
      <title>Turbocharger cross-section</title>

      {/* Exhaust manifold + housing — left side */}
      <g stroke="currentColor" strokeWidth="1.4" fill="none">
        {/* turbine housing volute outline */}
        <path d="M 30 60 Q 30 30 80 30 L 200 30 Q 230 30 230 65 L 230 215 Q 230 250 200 250 L 80 250 Q 30 250 30 220 Z" />
        {/* turbine exit pipe */}
        <path d="M 30 110 L 10 110 L 10 170 L 30 170" />
        {/* compressor housing outline (mirror) */}
        <path d="M 530 60 Q 530 30 480 30 L 360 30 Q 330 30 330 65 L 330 215 Q 330 250 360 250 L 480 250 Q 530 250 530 220 Z" />
        {/* compressor inlet pipe */}
        <path d="M 530 110 L 550 110 L 550 170 L 530 170" />
        {/* bearing housing (center) */}
        <rect x="234" y="115" width="92" height="50" rx="3" />
      </g>

      {/* Volute / scroll cross-section hatching */}
      <g stroke="currentColor" strokeWidth="0.5" opacity="0.35">
        <line x1="60" y1="60" x2="80" y2="80" />
        <line x1="60" y1="80" x2="80" y2="100" />
        <line x1="60" y1="200" x2="80" y2="180" />
        <line x1="60" y1="220" x2="80" y2="200" />
        <line x1="500" y1="60" x2="480" y2="80" />
        <line x1="500" y1="80" x2="480" y2="100" />
      </g>

      {/* Shaft connecting both wheels */}
      <rect
        x="220"
        y="135"
        width="120"
        height="10"
        fill="currentColor"
        opacity="0.85"
      />

      {/* Turbine wheel (left) — radial-inflow, blades inward */}
      <g>
        <circle
          cx="170"
          cy="140"
          r="56"
          fill="rgb(var(--surface-subtle))"
          stroke="currentColor"
          strokeWidth="1.4"
        />
        {/* 10 turbine blades */}
        {Array.from({ length: 10 }).map((_, i) => {
          const a = (i / 10) * 2 * Math.PI;
          const x1 = 170 + 18 * Math.cos(a);
          const y1 = 140 + 18 * Math.sin(a);
          const x2 = 170 + 54 * Math.cos(a + 0.35);
          const y2 = 140 + 54 * Math.sin(a + 0.35);
          return (
            <line
              key={i}
              x1={x1}
              y1={y1}
              x2={x2}
              y2={y2}
              stroke="currentColor"
              strokeWidth="1.4"
            />
          );
        })}
        <circle cx="170" cy="140" r="14" fill="currentColor" />
      </g>

      {/* Compressor wheel (right) — centrifugal, blades curving outward backward-swept */}
      <g>
        <circle
          cx="400"
          cy="140"
          r="56"
          fill="rgb(var(--surface-subtle))"
          stroke="currentColor"
          strokeWidth="1.4"
        />
        {Array.from({ length: 9 }).map((_, i) => {
          const a = (i / 9) * 2 * Math.PI;
          const r0 = 14;
          const r1 = 54;
          // back-swept curve
          const cx = 400 + (r0 + r1) * 0.5 * Math.cos(a);
          const cy = 140 + (r0 + r1) * 0.5 * Math.sin(a);
          const x1 = 400 + r0 * Math.cos(a);
          const y1 = 140 + r0 * Math.sin(a);
          const x2 = 400 + r1 * Math.cos(a - 0.4);
          const y2 = 140 + r1 * Math.sin(a - 0.4);
          return (
            <path
              key={i}
              d={`M ${x1} ${y1} Q ${cx + 4} ${cy} ${x2} ${y2}`}
              fill="none"
              stroke="currentColor"
              strokeWidth="1.4"
            />
          );
        })}
        <circle cx="400" cy="140" r="14" fill="currentColor" />
      </g>

      {/* Exhaust gas arrows (red/danger) */}
      <g
        stroke="rgb(var(--danger-default))"
        fill="rgb(var(--danger-default))"
        strokeWidth="1.6"
      >
        <path d="M 90 50 L 130 80 M 130 80 L 122 76 M 130 80 L 126 72" fill="none" />
        <path d="M 90 230 L 130 200 M 130 200 L 126 208 M 130 200 L 122 204" fill="none" />
        {/* exit arrow downward */}
        <path d="M 20 145 L 20 175 M 20 175 L 16 168 M 20 175 L 24 168" fill="none" />
      </g>

      {/* Intake air arrows (blue/info) */}
      <g
        stroke="rgb(var(--info-default))"
        fill="rgb(var(--info-default))"
        strokeWidth="1.6"
      >
        <path d="M 540 145 L 540 115 M 540 115 L 544 122 M 540 115 L 536 122" fill="none" />
        <path d="M 470 50 L 430 80 M 430 80 L 438 76 M 430 80 L 434 72" fill="none" />
        <path d="M 470 230 L 430 200 M 430 200 L 434 208 M 430 200 L 438 204" fill="none" />
      </g>

      {/* Labels */}
      <g
        fontFamily="var(--font-mono)"
        fontSize="10"
        fill="rgb(var(--text-muted))"
      >
        <text x="170" y="20" textAnchor="middle">
          Turbine wheel
        </text>
        <text x="400" y="20" textAnchor="middle">
          Compressor wheel
        </text>
        <text x="280" y="105" textAnchor="middle">
          Shaft
        </text>
        <text x="280" y="180" textAnchor="middle">
          Bearings
        </text>
        <text
          x="50"
          y="270"
          fill="rgb(var(--danger-text))"
          fontSize="11"
        >
          hot exhaust in
        </text>
        <text
          x="450"
          y="270"
          fill="rgb(var(--info-text))"
          fontSize="11"
          textAnchor="start"
        >
          cold air in
        </text>
      </g>
    </svg>
  );
}
