// Small line icons (stroke = currentColor), so colour comes from the text colour class.
const base = { fill: "none", stroke: "currentColor", strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": true };

export function LeafIcon({ className = "h-4 w-4" }) {
  return <svg viewBox="0 0 24 24" strokeWidth="2" className={className} {...base}><path d="M4 20c2-9 8-14 16-16-1 9-6 15-16 16z" /><path d="M4 20l9-9" /></svg>;
}

export function MailIcon({ className = "h-5 w-5" }) {
  return <svg viewBox="0 0 24 24" strokeWidth="2" className={className} {...base}><rect x="3" y="5" width="18" height="14" rx="3" /><path d="M3 7l9 6 9-6" /></svg>;
}

export function ArrowIcon({ className = "h-5 w-5" }) {
  return <svg viewBox="0 0 24 24" strokeWidth="2.4" className={className} {...base}><path d="M5 12h14M13 6l6 6-6 6" /></svg>;
}

export function BackIcon({ className = "h-5 w-5" }) {
  return <svg viewBox="0 0 24 24" strokeWidth="2.2" className={className} {...base}><path d="M19 12H5M11 6l-6 6 6 6" /></svg>;
}

export function MomoIcon({ className = "h-6 w-6" }) {
  return (
    <svg viewBox="0 0 52 44" strokeWidth="3" className={className} {...base}>
      <path d="M2 30 C2 44 50 44 50 30 C50 18 33 8 26 4 C19 8 2 18 2 30 Z" />
      <path d="M26 4 L20 17 M26 4 L26 18 M26 4 L32 17" />
    </svg>
  );
}

export function BurgerIcon({ className = "h-6 w-6" }) {
  return (
    <svg viewBox="0 0 52 46" strokeWidth="3" className={className} {...base}>
      <path d="M4 20 C4 4 48 4 48 20 Z" /><path d="M3 27 H49" /><path d="M5 33 H47 Q47 42 39 42 H13 Q5 42 5 33 Z" />
    </svg>
  );
}

export function FriesIcon({ className = "h-6 w-6" }) {
  return (
    <svg viewBox="0 0 52 56" strokeWidth="3" className={className} {...base}>
      <path d="M10 22 L15 52 H37 L42 22 Z" /><path d="M15 22 L12 4 M21 22 L20 1 M27 22 L28 2 M33 22 L36 5 M38 22 L42 9" />
    </svg>
  );
}

export function SandwichIcon({ className = "h-6 w-6" }) {
  return (
    <svg viewBox="0 0 56 44" strokeWidth="3" className={className} {...base}>
      <path d="M2 40 L28 3 L54 40 Z" /><path d="M8 34 H48" /><path d="M12 28 Q17 24 22 28 T32 28 T42 28" />
    </svg>
  );
}

export function PlateIcon({ className = "h-6 w-6" }) {
  return (
    <svg viewBox="0 0 24 24" strokeWidth="2" className={className} {...base}>
      <circle cx="12" cy="12" r="8" /><circle cx="12" cy="12" r="4" />
    </svg>
  );
}

export function ReceiptIcon({ className = "h-5 w-5" }) {
  return <svg viewBox="0 0 24 24" strokeWidth="2" className={className} {...base}><path d="M6 3h12v18l-3-2-3 2-3-2-3 2z" /><path d="M9 8h6M9 12h6" /></svg>;
}

export function UserIcon({ className = "h-5 w-5" }) {
  return <svg viewBox="0 0 24 24" strokeWidth="2" className={className} {...base}><circle cx="12" cy="8" r="4" /><path d="M4 21c1-4 4-6 8-6s7 2 8 6" /></svg>;
}

export function BagIcon({ className = "h-5 w-5" }) {
  return <svg viewBox="0 0 24 24" strokeWidth="2" className={className} {...base}><path d="M5 8h14l-1.5 12h-11z" /><path d="M9 8V6a3 3 0 0 1 6 0v2" /></svg>;
}

export function TrashIcon({ className = "h-[18px] w-[18px]" }) {
  return <svg viewBox="0 0 24 24" strokeWidth="2" className={className} {...base}><path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3" /></svg>;
}

export function CashIcon({ className = "h-5 w-5" }) {
  return <svg viewBox="0 0 24 24" strokeWidth="2" className={className} {...base}><rect x="2" y="6" width="20" height="12" rx="2" /><circle cx="12" cy="12" r="2.5" /></svg>;
}

export function PlusIcon({ className = "h-[18px] w-[18px]" }) {
  return <svg viewBox="0 0 24 24" strokeWidth="2.2" className={className} {...base}><path d="M12 5v14M5 12h14" /></svg>;
}

export function ListIcon({ className = "h-5 w-5" }) {
  return <svg viewBox="0 0 24 24" strokeWidth="2" className={className} {...base}><path d="M4 6h16M4 12h16M4 18h10" /></svg>;
}

export function ChartIcon({ className = "h-5 w-5" }) {
  return <svg viewBox="0 0 24 24" strokeWidth="2" className={className} {...base}><path d="M4 20V10M10 20V4M16 20v-7M22 20H2" /></svg>;
}

export function StarIcon({ className = "h-5 w-5" }) {
  return <svg viewBox="0 0 24 24" strokeWidth="2" className={className} {...base}><path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z" /></svg>;
}

export function BellIcon({ off = false, className = "h-[18px] w-[18px]" }) {
  return (
    <svg viewBox="0 0 24 24" strokeWidth="2" className={className} {...base}>
      <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" /><path d="M10 21h4" />{off && <path d="M3 3l18 18" />}
    </svg>
  );
}

export function NoteIcon({ className = "h-4 w-4" }) {
  return <svg viewBox="0 0 24 24" strokeWidth="2" className={className} {...base}><path d="M5 4h14v12l-4 4H5z" /><path d="M9 9h6M9 13h4" /></svg>;
}

export function PhoneIcon({ className = "h-[18px] w-[18px]" }) {
  return <svg viewBox="0 0 24 24" strokeWidth="2" className={className} {...base}><path d="M5 4h4l2 5-3 2a11 11 0 0 0 5 5l2-3 5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2" /></svg>;
}

export function CheckIcon({ className = "h-4 w-4" }) {
  return <svg viewBox="0 0 24 24" strokeWidth="3" className={className} {...base}><path d="M5 12l5 5 9-10" /></svg>;
}

export function ClockIcon({ className = "h-5 w-5" }) {
  return <svg viewBox="0 0 24 24" strokeWidth="2" className={className} {...base}><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></svg>;
}

export function ShakeIcon({ className = "h-6 w-6" }) {
  return (
    <svg viewBox="0 0 48 60" strokeWidth="3.2" className={className} {...base}>
      <path d="M10 20 L15 56 H33 L38 20 Z" /><path d="M7 20 H41 M12 20 C12 9 36 9 36 20" /><path d="M28 11 L36 2" />
    </svg>
  );
}

// Icon for a menu category. Categories are free text, so unknown ones get a plain plate.
const BY_CATEGORY = { momos: MomoIcon, fries: FriesIcon, burgers: BurgerIcon, sandwiches: SandwichIcon, shakes: ShakeIcon };
export function CategoryIcon({ category, className }) {
  const Icon = BY_CATEGORY[String(category).toLowerCase()] || PlateIcon;
  return <Icon className={className} />;
}
