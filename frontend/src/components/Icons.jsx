/**
 * Shared icon set — clean Lucide-style stroke icons (currentColor, 1.75 stroke)
 * plus the brand logo mark. SVG, never emoji, so they scale crisply, theme with
 * the surrounding text color, and stay consistent across the product.
 */

function Svg({ size = 20, children, fill = 'none', stroke = true, ...rest }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill={fill}
      stroke={stroke ? 'currentColor' : 'none'}
      strokeWidth={stroke ? 1.75 : 0}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      {children}
    </svg>
  );
}

export const ChevronDown = (p) => (
  <Svg {...p}><path d="M6 9l6 6 6-6" /></Svg>
);

export const Sparkle = (p) => (
  <Svg {...p}>
    <path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3z" />
  </Svg>
);

export const ShieldCheck = (p) => (
  <Svg {...p}>
    <path d="M12 3l7 3v5c0 4.4-3 8-7 10-4-2-7-5.6-7-10V6l7-3z" />
    <path d="M9 12l2 2 4-4" />
  </Svg>
);

export const AlertTriangle = (p) => (
  <Svg {...p}>
    <path d="M10.3 4.3L2.5 18a2 2 0 0 0 1.7 3h15.6a2 2 0 0 0 1.7-3L13.7 4.3a2 2 0 0 0-3.4 0z" />
    <path d="M12 9v4" />
    <path d="M12 17h.01" />
  </Svg>
);

export const Send = (p) => (
  <Svg {...p}>
    <path d="M22 2L11 13" />
    <path d="M22 2l-7 20-4-9-9-4 20-7z" />
  </Svg>
);

export const Plus = (p) => (
  <Svg {...p}><path d="M12 5v14M5 12h14" /></Svg>
);

export const User = (p) => (
  <Svg {...p}>
    <path d="M20 21a8 8 0 0 0-16 0" />
    <circle cx="12" cy="8" r="4" />
  </Svg>
);

export const LogOut = (p) => (
  <Svg {...p}>
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
    <path d="M16 17l5-5-5-5" />
    <path d="M21 12H9" />
  </Svg>
);

export const Menu = (p) => (
  <Svg {...p}><path d="M3 6h18M3 12h18M3 18h18" /></Svg>
);

export const Close = (p) => (
  <Svg {...p}><path d="M18 6L6 18M6 6l12 12" /></Svg>
);

export const BookOpen = (p) => (
  <Svg {...p}>
    <path d="M12 7v14" />
    <path d="M3 18a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z" />
  </Svg>
);

export const Users = (p) => (
  <Svg {...p}>
    <path d="M17 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
    <circle cx="9.5" cy="7" r="4" />
    <path d="M22 21v-2a4 4 0 0 0-3-3.9" />
    <path d="M16 3.1a4 4 0 0 1 0 7.8" />
  </Svg>
);

export const BadgeCheck = (p) => (
  <Svg {...p}>
    <path d="M3.9 8.5a3 3 0 0 1 2-2 3 3 0 0 1 1.8-2.6 3 3 0 0 1 2.9.2 3 3 0 0 1 3.2 0 3 3 0 0 1 2.9-.2A3 3 0 0 1 18 6.5a3 3 0 0 1 2 2 3 3 0 0 1-.2 2.9 3 3 0 0 1 0 3.2 3 3 0 0 1 .2 2.9 3 3 0 0 1-2 2 3 3 0 0 1-1.8 2.6 3 3 0 0 1-2.9-.2 3 3 0 0 1-3.2 0 3 3 0 0 1-2.9.2A3 3 0 0 1 5.9 21a3 3 0 0 1-2-2 3 3 0 0 1 .2-2.9 3 3 0 0 1 0-3.2 3 3 0 0 1-.2-2.4z" />
    <path d="M9 12l2 2 4-4" />
  </Svg>
);

export const ExternalLink = (p) => (
  <Svg {...p}>
    <path d="M15 3h6v6" />
    <path d="M10 14L21 3" />
    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
  </Svg>
);

export const MessageHeart = (p) => (
  <Svg {...p}>
    <path d="M21 11.5a8.5 8.5 0 0 1-11.7 7.9L3 21l1.6-6.3A8.5 8.5 0 1 1 21 11.5z" />
    <path d="M12 14.2l-2-1.9a1.5 1.5 0 0 1 2-2.2 1.5 1.5 0 0 1 2 2.2l-2 1.9z" fill="currentColor" stroke="none" />
  </Svg>
);

export const HeartPulse = (p) => (
  <Svg {...p}>
    <path d="M20.4 6.6a5 5 0 0 0-7-.2L12 7.8l-1.4-1.4a5 5 0 0 0-7.1 7l7.1 7.1a2 2 0 0 0 2.8 0l7-7a5 5 0 0 0 0-6.9z" />
    <path d="M3 13h3l1.5-3 2.5 5 1.5-3H15" />
  </Svg>
);

export const Home = (p) => (
  <Svg {...p}>
    <path d="M3 10.5L12 3l9 7.5" />
    <path d="M5 9.5V20a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V9.5" />
    <path d="M9.5 21v-6h5v6" />
  </Svg>
);

export const Settings = (p) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H10a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V10a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
  </Svg>
);

export const Pencil = (p) => (
  <Svg {...p}>
    <path d="M12 20h9" />
    <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z" />
  </Svg>
);

export const Trash = (p) => (
  <Svg {...p}>
    <path d="M3 6h18" />
    <path d="M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2" />
    <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
  </Svg>
);

export const ChevronRight = (p) => (
  <Svg {...p}><path d="M9 6l6 6-6 6" /></Svg>
);

export const ArrowRight = (p) => (
  <Svg {...p}><path d="M5 12h14" /><path d="M13 6l6 6-6 6" /></Svg>
);

export const Check = (p) => (
  <Svg {...p}><path d="M5 12l5 5L20 7" /></Svg>
);

/** Kakao speech-bubble glyph (mono, for the login button). */
export const KakaoGlyph = (p) => (
  <Svg {...p} fill="currentColor" stroke={false}>
    <path d="M12 4C7 4 3 7.1 3 11c0 2.5 1.7 4.7 4.2 5.9-.2.6-.7 2.5-.8 2.9 0 .3.2.3.4.2.2-.1 2.6-1.7 3.6-2.4.5.1 1 .1 1.6.1 5 0 9-3.1 9-7 0-3.9-4-7-9-7z" />
  </Svg>
);

/** Naver 'N' glyph (mono, for the login button). */
export const NaverGlyph = (p) => (
  <Svg {...p} fill="currentColor" stroke={false}>
    <path d="M5 4h4.3l4.1 6V4H19v16h-4.3l-4.1-6v6H5V4z" />
  </Svg>
);

/**
 * Brand logo mark — a warm "roundtable" squircle: a soft heart at the center
 * ringed by three dots (the AI panel gathered around one answer).
 */
export function Logo({ size = 36 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        <linearGradient id="pr-logo-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#EC7FA3" />
          <stop offset="1" stopColor="#C9426E" />
        </linearGradient>
      </defs>
      <rect x="2" y="2" width="44" height="44" rx="14" fill="url(#pr-logo-g)" />
      <path
        d="M24 33.5l-7-6.4a4.6 4.6 0 0 1 6.3-6.7l.7.7.7-.7a4.6 4.6 0 0 1 6.3 6.7l-7 6.4z"
        fill="#fff"
      />
      <circle cx="24" cy="11.5" r="2.4" fill="#fff" opacity="0.95" />
      <circle cx="11.8" cy="20" r="2.1" fill="#fff" opacity="0.7" />
      <circle cx="36.2" cy="20" r="2.1" fill="#fff" opacity="0.7" />
    </svg>
  );
}
