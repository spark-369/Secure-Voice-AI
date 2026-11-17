/** Pill-style label (severity, roles, status). */
export default function Badge({ className = '', children }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-medium ${className}`}
    >
      {children}
    </span>
  )
}
