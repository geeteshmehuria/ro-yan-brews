// A bamboo steamer of momos with chopsticks: the menu hero's picture. Colours are theme tokens.
export function SteamerArt({ className }) {
  return (
    <svg viewBox="0 0 360 230" className={className} aria-hidden="true">
      <g fill="none" stroke="var(--text)" strokeOpacity="0.45" strokeWidth="4" strokeLinecap="round">
        <path d="M120 70 C135 50 105 40 120 18" /><path d="M180 62 C195 42 165 32 180 8" /><path d="M240 70 C255 50 225 40 240 18" />
      </g>
      <path d="M30 140 H330 V182 Q330 214 298 214 H62 Q30 214 30 182 Z" fill="var(--wood)" />
      <path d="M30 160 H330 M30 180 H330 M30 198 H322" stroke="var(--wood-dark)" strokeWidth="4" />
      <ellipse cx="180" cy="140" rx="150" ry="30" fill="var(--wood-light)" />
      <ellipse cx="180" cy="138" rx="134" ry="22" fill="var(--wood-inside)" />
      <g stroke="var(--dough-line)" strokeWidth="3" strokeLinecap="round" fill="var(--dough)">
        <path d="M70 140 C70 102 120 96 118 74 C140 90 166 104 166 140 Z" />
        <path d="M118 74 L106 112 M118 74 L120 114 M118 74 L134 110" fill="none" />
        <path d="M150 136 C150 92 206 84 206 58 C230 76 256 92 256 136 Z" />
        <path d="M206 58 L190 104 M206 58 L206 106 M206 58 L222 102" fill="none" />
        <path d="M232 142 C232 108 270 100 272 80 C292 96 306 110 306 142 Z" />
        <path d="M272 80 L262 114 M272 80 L274 116 M272 80 L288 112" fill="none" />
      </g>
      <g stroke="var(--accent)" strokeWidth="7" strokeLinecap="round"><path d="M250 30 L344 120" /><path d="M268 20 L352 104" /></g>
    </svg>
  );
}
