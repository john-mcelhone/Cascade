/**
 * Side-by-side diagram contrasting radial (centrifugal) vs axial machine
 * geometry. Used in Chapter 4 to motivate the specific-speed argument:
 * same job, different shape.
 *
 * Left: a centrifugal compressor — air enters axially, leaves radially.
 * Right: an axial compressor with three stages — air enters and leaves
 * parallel to the shaft.
 */
export function TurboVsJet({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 720 320"
      className={className}
      role="img"
      aria-label="Side-by-side cross-section of a centrifugal (radial) compressor and an axial multi-stage compressor."
    >
      <title>Radial vs axial geometry</title>

      {/* === LEFT: Centrifugal (radial) === */}
      <g>
        <text
          x="160"
          y="32"
          textAnchor="middle"
          fontSize="13"
          fontFamily="var(--font-sans)"
          fontWeight="500"
          fill="rgb(var(--text-default))"
        >
          Centrifugal compressor
        </text>
        <text
          x="160"
          y="50"
          textAnchor="middle"
          fontSize="10"
          fontFamily="var(--font-mono)"
          fill="rgb(var(--text-muted))"
        >
          radial · n_s ≈ 0.4 – 1.0
        </text>

        {/* outer housing (volute) */}
        <g stroke="currentColor" strokeWidth="1.4" fill="none">
          <path d="M 60 200 Q 60 130 110 130 L 210 130 Q 260 130 260 200 L 260 250 Q 260 290 220 290 L 100 290 Q 60 290 60 250 Z" />
          {/* axis */}
          <line
            x1="20"
            y1="270"
            x2="300"
            y2="270"
            strokeDasharray="3 4"
            strokeWidth="0.8"
          />
        </g>

        {/* impeller blades (back-swept) */}
        <g>
          <circle
            cx="160"
            cy="210"
            r="60"
            fill="rgb(var(--surface-subtle))"
            stroke="currentColor"
            strokeWidth="1.4"
          />
          {Array.from({ length: 10 }).map((_, i) => {
            const a = (i / 10) * 2 * Math.PI;
            const x1 = 160 + 14 * Math.cos(a);
            const y1 = 210 + 14 * Math.sin(a);
            const x2 = 160 + 58 * Math.cos(a - 0.45);
            const y2 = 210 + 58 * Math.sin(a - 0.45);
            return (
              <path
                key={i}
                d={`M ${x1} ${y1} Q ${160 + 38 * Math.cos(a - 0.15)} ${210 + 38 * Math.sin(a - 0.15)} ${x2} ${y2}`}
                fill="none"
                stroke="currentColor"
                strokeWidth="1.4"
              />
            );
          })}
          <circle cx="160" cy="210" r="14" fill="currentColor" />
        </g>

        {/* axial in (info), radial out (info) */}
        <g
          stroke="rgb(var(--info-default))"
          strokeWidth="1.6"
          fill="rgb(var(--info-default))"
        >
          <path d="M 160 90 L 160 130" fill="none" />
          <polyline points="155 124, 160 130, 165 124" fill="none" />
          <path d="M 250 180 L 290 180" fill="none" />
          <polyline points="284 174, 290 180, 284 186" fill="none" />
        </g>
        <text
          x="160"
          y="85"
          textAnchor="middle"
          fontSize="10"
          fontFamily="var(--font-mono)"
          fill="rgb(var(--info-text))"
        >
          axial in
        </text>
        <text
          x="295"
          y="170"
          textAnchor="start"
          fontSize="10"
          fontFamily="var(--font-mono)"
          fill="rgb(var(--info-text))"
        >
          radial out
        </text>
        <text
          x="160"
          y="310"
          textAnchor="middle"
          fontSize="10"
          fontFamily="var(--font-sans)"
          fill="rgb(var(--text-muted))"
        >
          one stage delivers PR ≈ 2 – 5
        </text>
      </g>

      {/* === RIGHT: Axial multi-stage === */}
      <g transform="translate(360 0)">
        <text
          x="160"
          y="32"
          textAnchor="middle"
          fontSize="13"
          fontFamily="var(--font-sans)"
          fontWeight="500"
          fill="rgb(var(--text-default))"
        >
          Axial compressor
        </text>
        <text
          x="160"
          y="50"
          textAnchor="middle"
          fontSize="10"
          fontFamily="var(--font-mono)"
          fill="rgb(var(--text-muted))"
        >
          axial · n_s ≈ 1.0 – 3.0
        </text>

        {/* casing */}
        <g fill="none" stroke="currentColor" strokeWidth="1.4">
          <path d="M 30 150 L 290 175 L 290 240 L 30 220 Z" />
          {/* hub line */}
          <line
            x1="20"
            y1="260"
            x2="300"
            y2="260"
            strokeDasharray="3 4"
            strokeWidth="0.8"
          />
        </g>

        {/* 6 alternating stator / rotor stages */}
        {[40, 80, 120, 160, 200, 240].map((x, i) => {
          const isRotor = i % 2 === 0;
          const yTop = 152 + i * 4;
          const yBot = 220 + Math.floor(i / 2) * 3;
          return (
            <g key={x} stroke="currentColor" strokeWidth="1.4">
              {Array.from({ length: 6 }).map((_, k) => (
                <line
                  key={k}
                  x1={x}
                  y1={yTop + k * 11}
                  x2={x + (isRotor ? 5 : -5)}
                  y2={yTop + k * 11 - (isRotor ? 4 : -4)}
                />
              ))}
              <text
                x={x + (isRotor ? 2 : -2)}
                y={yBot + 28}
                textAnchor="middle"
                fontSize="9"
                fontFamily="var(--font-mono)"
                fill="rgb(var(--text-muted))"
              >
                {isRotor ? "R" : "S"}
              </text>
            </g>
          );
        })}

        {/* axial flow arrow */}
        <g
          stroke="rgb(var(--info-default))"
          strokeWidth="1.6"
          fill="rgb(var(--info-default))"
        >
          <path d="M 5 195 L 25 195" fill="none" />
          <polyline points="19 189, 25 195, 19 201" fill="none" />
          <path d="M 295 210 L 320 210" fill="none" />
          <polyline points="314 204, 320 210, 314 216" fill="none" />
        </g>
        <text
          x="0"
          y="187"
          textAnchor="start"
          fontSize="10"
          fontFamily="var(--font-mono)"
          fill="rgb(var(--info-text))"
        >
          in
        </text>
        <text
          x="325"
          y="200"
          textAnchor="start"
          fontSize="10"
          fontFamily="var(--font-mono)"
          fill="rgb(var(--info-text))"
        >
          out
        </text>
        <text
          x="160"
          y="310"
          textAnchor="middle"
          fontSize="10"
          fontFamily="var(--font-sans)"
          fill="rgb(var(--text-muted))"
        >
          each stage PR ≈ 1.1 – 1.5 · stacked many over
        </text>
      </g>
    </svg>
  );
}
