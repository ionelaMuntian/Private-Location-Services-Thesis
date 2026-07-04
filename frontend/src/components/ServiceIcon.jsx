const PIN_PATH =
  "M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z";

function Pin({ x, y, scale = 1, opacity = 1 }) {
  return (
    <g transform={`translate(${x}, ${y}) scale(${scale})`} opacity={opacity}>
      <path d={PIN_PATH} fill="currentColor" fillRule="evenodd" />
    </g>
  );
}

const icons = {
  poi: (
    <>
      <circle cx="32" cy="22" r="18" stroke="currentColor" strokeWidth="1.3" strokeDasharray="3 4" opacity="0.45" />
      <circle cx="32" cy="22" r="10" stroke="currentColor" strokeWidth="1.3" strokeDasharray="3 4" opacity="0.7" />
      <circle cx="32" cy="22" r="3.5" fill="currentColor" />
      <circle cx="11" cy="9" r="2.2" fill="currentColor" opacity="0.55" />
      <circle cx="53" cy="11" r="2.2" fill="currentColor" opacity="0.55" />
      <circle cx="47" cy="35" r="2.2" fill="currentColor" opacity="0.55" />
    </>
  ),
  sharing: (
    <>
      <path d="M16 23C23 9 42 6 45 18" stroke="currentColor" strokeWidth="1.4" strokeDasharray="3 4" fill="none" strokeLinecap="round" opacity="0.85" />
      <Pin x={5} y={2} scale={0.95} />
      <Pin x={36} y={0} scale={0.8} opacity={0.8} />
    </>
  ),
  anomaly: (
    <>
      <circle cx="32" cy="26" r="16" stroke="currentColor" strokeWidth="1.3" opacity="0.5" fill="none" />
      <ellipse cx="32" cy="26" rx="6.5" ry="16" stroke="currentColor" strokeWidth="1" opacity="0.35" fill="none" />
      <path d="M16 26h32" stroke="currentColor" strokeWidth="1" opacity="0.3" fill="none" />
      <path d="M19 16c7 5 19 5 26 0" stroke="currentColor" strokeWidth="1" opacity="0.28" fill="none" />
      <path d="M19 36c7-5 19-5 26 0" stroke="currentColor" strokeWidth="1" opacity="0.28" fill="none" />
      <path d="M20 15C26 3 48 8 46 30" stroke="currentColor" strokeWidth="1.4" strokeDasharray="3 3" fill="none" />
      <circle cx="20" cy="15" r="2.8" fill="currentColor" />
      <circle cx="46" cy="30" r="2.8" fill="currentColor" />
      <g stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" opacity="0.85">
        <line x1="34" y1="2" x2="34" y2="9" />
        <line x1="30.5" y1="5.5" x2="37.5" y2="5.5" />
      </g>
    </>
  ),
  stats: (
    <>
      <rect x="9" y="26" width="9" height="16" rx="1.5" fill="currentColor" opacity="0.5" />
      <rect x="24" y="16" width="9" height="26" rx="1.5" fill="currentColor" opacity="0.7" />
      <rect x="39" y="21" width="9" height="21" rx="1.5" fill="currentColor" opacity="0.6" />
      <rect x="54" y="9" width="9" height="33" rx="1.5" fill="currentColor" opacity="0.9" />
      <path d="M9 23L24 13L39 18L54 6" stroke="currentColor" strokeWidth="1.3" fill="none" opacity="0.9" />
      <circle cx="54" cy="6" r="2.2" fill="currentColor" />
    </>
  ),
};

export default function ServiceIcon({ name }) {
  return (
    <svg className="service-icon" viewBox="0 0 64 48" width="80" height="60" fill="none" aria-hidden="true">
      {icons[name]}
    </svg>
  );
}
