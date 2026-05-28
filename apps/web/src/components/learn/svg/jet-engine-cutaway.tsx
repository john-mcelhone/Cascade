/**
 * Simplified jet engine cutaway, used in Chapter 2 to anchor the four
 * Brayton stations: 1 (compressor inlet), 2 (compressor exit / combustor
 * inlet), 3 (turbine inlet, post-combustion), 4 (turbine exit / nozzle).
 *
 * The geometry is schematic — fan + compressor + combustor + turbine +
 * nozzle laid out along the engine axis. Numbers correspond to the
 * canonical SAE / Walsh-Fletcher station-numbering used throughout the
 * chapter.
 */
export function JetEngineCutaway({
  className,
}: {
  className?: string;
}) {
  return (
    <svg
      viewBox="0 0 720 240"
      className={className}
      role="img"
      aria-label="Simplified jet engine cutaway showing fan, compressor, combustor, turbine, and nozzle along the engine axis. The four Brayton-cycle stations are labelled."
    >
      <title>Jet engine cutaway with Brayton stations</title>

      {/* Engine outer cowl */}
      <g fill="none" stroke="currentColor" strokeWidth="1.4">
        <path d="M 30 90 L 100 80 L 200 80 L 260 65 L 400 65 L 460 80 L 560 80 L 660 90 L 700 100 L 700 140 L 660 150 L 560 160 L 460 160 L 400 175 L 260 175 L 200 160 L 100 160 L 30 150 Z" />
        {/* center body / spinner */}
        <ellipse cx="58" cy="120" rx="28" ry="20" />
        {/* axis */}
        <line
          x1="0"
          y1="120"
          x2="720"
          y2="120"
          strokeDasharray="3 4"
          strokeWidth="0.8"
        />
      </g>

      {/* Fan (upstream) */}
      <g stroke="currentColor" strokeWidth="1.4">
        {Array.from({ length: 7 }).map((_, i) => (
          <line
            key={i}
            x1="95"
            y1={85 + i * 12}
            x2="115"
            y2={75 + i * 12}
          />
        ))}
      </g>

      {/* Compressor stages — 6 stages */}
      <g stroke="currentColor" strokeWidth="1.4">
        {[140, 160, 180, 200, 220, 240].map((x) => (
          <g key={x}>
            <line x1={x} y1="85" x2={x} y2="155" strokeOpacity="0.6" />
            {Array.from({ length: 8 }).map((_, i) => (
              <line
                key={i}
                x1={x}
                y1={85 + i * 9}
                x2={x + 6}
                y2={80 + i * 9}
              />
            ))}
          </g>
        ))}
      </g>

      {/* Combustor */}
      <g>
        <rect
          x="280"
          y="80"
          width="100"
          height="80"
          rx="6"
          fill="rgb(var(--warning-surface))"
          stroke="rgb(var(--warning-default))"
          strokeWidth="1.4"
          opacity="0.95"
        />
        {/* flame zigzag */}
        <path
          d="M 295 130 L 305 95 L 315 130 L 325 95 L 335 130 L 345 95 L 355 130 L 365 95"
          fill="none"
          stroke="rgb(var(--danger-default))"
          strokeWidth="1.6"
        />
      </g>

      {/* Turbine stages — 3 stages */}
      <g stroke="currentColor" strokeWidth="1.4">
        {[430, 470, 510].map((x) => (
          <g key={x}>
            <line x1={x} y1="85" x2={x} y2="155" strokeOpacity="0.6" />
            {Array.from({ length: 8 }).map((_, i) => (
              <line
                key={i}
                x1={x}
                y1={85 + i * 9}
                x2={x + 7}
                y2={80 + i * 9}
              />
            ))}
          </g>
        ))}
      </g>

      {/* Nozzle */}
      <g fill="none" stroke="currentColor" strokeWidth="1.4">
        <path d="M 560 90 L 660 105" />
        <path d="M 560 150 L 660 135" />
      </g>

      {/* Exhaust arrow */}
      <g stroke="rgb(var(--danger-default))" strokeWidth="2" fill="none">
        <line x1="680" y1="120" x2="715" y2="120" />
        <polyline points="708 114, 715 120, 708 126" />
      </g>

      {/* Inlet arrow */}
      <g stroke="rgb(var(--info-default))" strokeWidth="2" fill="none">
        <line x1="0" y1="120" x2="28" y2="120" />
        <polyline points="22 114, 28 120, 22 126" />
      </g>

      {/* Station markers */}
      <Station x={130} label="1" caption="inlet" />
      <Station x={260} label="2" caption="compressor exit" />
      <Station x={400} label="3" caption="turbine inlet" />
      <Station x={550} label="4" caption="turbine exit" />

      {/* Component labels */}
      <g
        fontFamily="var(--font-sans)"
        fontSize="11"
        fill="rgb(var(--text-muted))"
        textAnchor="middle"
      >
        <text x="100" y="210">
          Fan / compressor
        </text>
        <text x="330" y="210">
          Combustor
        </text>
        <text x="470" y="210">
          Turbine
        </text>
        <text x="610" y="210">
          Nozzle
        </text>
      </g>
    </svg>
  );
}

function Station({
  x,
  label,
  caption,
}: {
  x: number;
  label: string;
  caption: string;
}) {
  return (
    <g>
      <line
        x1={x}
        y1="55"
        x2={x}
        y2="185"
        stroke="rgb(var(--brand-default))"
        strokeWidth="1"
        strokeDasharray="2 2"
        opacity="0.7"
      />
      <circle
        cx={x}
        cy="42"
        r="9"
        fill="rgb(var(--brand-default))"
        stroke="rgb(var(--brand-default))"
        strokeWidth="1"
      />
      <text
        x={x}
        y="46"
        textAnchor="middle"
        fontSize="11"
        fontFamily="var(--font-mono)"
        fill="rgb(var(--text-inverse))"
        fontWeight="600"
      >
        {label}
      </text>
      <text
        x={x}
        y="26"
        textAnchor="middle"
        fontSize="9"
        fontFamily="var(--font-mono)"
        fill="rgb(var(--text-muted))"
      >
        {caption}
      </text>
    </g>
  );
}
