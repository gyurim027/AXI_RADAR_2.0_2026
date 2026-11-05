// 소개 모달의 단계별 그림. 장식이라 스크린 리더에는 숨긴다.
const P = { width: 72, height: 72, viewBox: '0 0 72 72', fill: 'none', 'aria-hidden': true, focusable: 'false' };
const STROKE = { stroke: 'url(#wg)', strokeWidth: 4, strokeLinecap: 'round', strokeLinejoin: 'round' };

function Defs() {
  return (
    <defs>
      <linearGradient id="wg" x1="8" y1="8" x2="64" y2="64" gradientUnits="userSpaceOnUse">
        <stop stopColor="#2f7bff" />
        <stop offset="1" stopColor="#7a4dff" />
      </linearGradient>
    </defs>
  );
}

const ART = {
  intro: (
    <svg {...P}><Defs />
      <circle cx="36" cy="36" r="26" {...STROKE} />
      <circle cx="36" cy="36" r="14" {...STROKE} opacity=".55" />
      <path d="M36 36 L56 20" {...STROKE} />
      <circle cx="36" cy="36" r="3.5" fill="url(#wg)" />
      <circle cx="50" cy="46" r="3" fill="url(#wg)" />
    </svg>
  ),
  solution: (
    <svg {...P}><Defs />
      <rect x="10" y="10" width="22" height="22" rx="6" {...STROKE} />
      <rect x="40" y="10" width="22" height="22" rx="6" fill="url(#wg)" opacity=".85" />
      <rect x="10" y="40" width="22" height="22" rx="6" fill="url(#wg)" opacity=".45" />
      <rect x="40" y="40" width="22" height="22" rx="6" {...STROKE} />
    </svg>
  ),
  effect: (
    <svg {...P}><Defs />
      <path d="M10 52 L26 36 L38 44 L60 18" {...STROKE} />
      <path d="M46 18 H60 V32" {...STROKE} />
      <path d="M16 16 v8 M12 20 h8" {...STROKE} strokeWidth="3" opacity=".6" />
    </svg>
  ),
  flow: (
    <svg {...P}><Defs />
      <path d="M12 52 H30 V34 H48 V18" {...STROKE} />
      <circle cx="12" cy="52" r="5" fill="url(#wg)" />
      <circle cx="30" cy="34" r="5" fill="url(#wg)" />
      <circle cx="48" cy="18" r="5" fill="url(#wg)" />
      <path d="M58 12 l4 4 l-4 4" {...STROKE} strokeWidth="3" />
    </svg>
  ),
  done: (
    <svg {...P}><Defs />
      <circle cx="36" cy="36" r="26" {...STROKE} />
      <path d="M24 37 L33 46 L50 26" {...STROKE} />
    </svg>
  ),
  next: (
    <svg {...P}><Defs />
      <path d="M20 54 L54 20" {...STROKE} />
      <path d="M32 20 H54 V42" {...STROKE} />
      <path d="M14 30 l3 6 l6 3 l-6 3 l-3 6 l-3 -6 l-6 -3 l6 -3 z" fill="url(#wg)" opacity=".7" />
    </svg>
  ),
  team: (
    <svg {...P}><Defs />
      <circle cx="26" cy="26" r="9" {...STROKE} />
      <path d="M10 56 c2 -12 10 -16 16 -16 s14 4 16 16" {...STROKE} />
      <circle cx="48" cy="30" r="7" fill="url(#wg)" opacity=".8" />
      <path d="M40 56 c1 -8 5 -12 10 -12 s9 4 11 12" {...STROKE} strokeWidth="3.5" opacity=".6" />
    </svg>
  ),
};

export function StepArt({ name }) {
  return ART[name] || ART.flow || null;
}

/** 카드 밖에 떠 있는 장식 도형 */
export function Star({ className }) {
  return (
    <svg className={className} width="46" height="46" viewBox="0 0 46 46" aria-hidden="true" focusable="false">
      <g stroke="#4d7cff" strokeWidth="7" strokeLinecap="round">
        <path d="M23 4 V42" /><path d="M6.5 13.5 L39.5 32.5" /><path d="M39.5 13.5 L6.5 32.5" />
      </g>
    </svg>
  );
}

export function Burst({ className }) {
  return (
    <svg className={className} width="44" height="44" viewBox="0 0 44 44" aria-hidden="true" focusable="false">
      <g stroke="#c9b6ff" strokeWidth="6" strokeLinecap="round">
        <path d="M6 38 L22 22" /><path d="M24 40 L34 20" /><path d="M10 20 L30 10" />
      </g>
    </svg>
  );
}
