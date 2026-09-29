export function Back({ onClick, children = "← Back" }) {
  return (
    <button onClick={onClick} className="press px-1 py-4 font-extrabold text-accent">{children}</button>
  );
}

export function BigButton({ onClick, disabled, children }) {
  return (
    <button onClick={onClick} disabled={disabled}
      className="press mt-3 w-full rounded-glass bg-accent p-4 text-lg font-black text-bg1 shadow-[0_8px_30px_rgba(56,189,248,0.35)] disabled:opacity-50">
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
