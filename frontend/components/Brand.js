// The Ashoka Chakra — 24-spoke navy wheel. Used as a national motif.
// (The State Emblem with the four lions is legally protected under the State
//  Emblem of India Act, 2005, so we deliberately use the Chakra instead.)
export function Chakra({ size = 28, className = "", spin = false }) {
  const spokes = Array.from({ length: 24 }, (_, i) => i * 15);
  return (
    <svg
      viewBox="0 0 100 100"
      width={size}
      height={size}
      className={`${spin ? "spin-slow" : ""} ${className}`}
      aria-label="Ashoka Chakra"
      role="img"
    >
      <circle cx="50" cy="50" r="46" fill="none" stroke="currentColor" strokeWidth="5" />
      <circle cx="50" cy="50" r="7" fill="currentColor" />
      {spokes.map((deg) => (
        <line
          key={deg}
          x1="50"
          y1="50"
          x2="50"
          y2="8"
          stroke="currentColor"
          strokeWidth="1.6"
          transform={`rotate(${deg} 50 50)`}
        />
      ))}
    </svg>
  );
}

// Full brand lockup: chakra + Adhikar.AI wordmark.
export function Logo({ compact = false }) {
  return (
    <div className="flex items-center gap-3">
      <div className="grid h-11 w-11 place-items-center rounded-lg bg-ashoka text-white shadow-sm">
        <Chakra size={26} className="text-white" />
      </div>
      <div className="leading-tight">
        <div className="text-lg font-bold tracking-tight text-ashoka">
          Adhikar<span className="text-saffron-600">.AI</span>
        </div>
        {!compact && (
          <div className="text-[11px] font-medium text-ink-soft">
            अधिकार · Scheme Access Copilot
          </div>
        )}
      </div>
    </div>
  );
}

// The thin national identity bar that sits above the app header.
export function GovStrip() {
  return (
    <>
      <div className="tricolour" />
      <div className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-6 py-1.5 text-[11px] text-ink-soft">
          <div className="flex items-center gap-2">
            <Chakra size={14} className="text-ashoka" />
            <span className="font-medium text-ink">भारत सरकार · Government of India</span>
          </div>
          <div className="hidden sm:block">
            A Digital India · CSC e-Governance concept
          </div>
        </div>
      </div>
    </>
  );
}
