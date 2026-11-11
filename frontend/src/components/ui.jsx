// The stall's logo (public/logo.png). It is drawn on white, so it sits on a white rounded tile.
export function Logo({ className = "h-10 w-10" }) {
  return <img src="/logo.png" alt="Mr. Momo" className={`flex-none rounded-2xl bg-white object-contain ${className}`} />;
}

// The food-doodle pattern behind a whole screen (.food-bg in index.css).
export function FoodBackground() {
  return <div aria-hidden="true" className="food-bg pointer-events-none fixed inset-0 -z-10" />;
}

// The Indian "veg" mark: a green dot in a green square.
export function VegMark() {
  return (
    <span aria-label="Veg" title="Veg" className="flex h-3.5 w-3.5 flex-none items-center justify-center rounded-[3px] border-[1.5px] border-accent2">
      <span className="h-1.5 w-1.5 rounded-full bg-accent2" />
    </span>
  );
}

export function Back({ onClick, children = "← Back" }) {
  return (
    <button onClick={onClick} className="press px-1 py-4 font-extrabold text-accent">{children}</button>
  );
}

export function BigButton({ onClick, disabled, children }) {
  return (
    <button onClick={onClick} disabled={disabled}
      className="press mt-3 w-full rounded-glass bg-accent p-4 text-lg font-black text-bg1 shadow-[0_8px_30px_var(--accent-glow)] disabled:opacity-50">
      {children}
    </button>
  );
}

export function Field(props) {
  return (
    <input {...props}
      className="glass my-3 w-full p-4 text-center text-xl tracking-[3px] text-ink placeholder:tracking-normal placeholder:text-muted focus:border-accent focus:outline-none" />
  );
}
