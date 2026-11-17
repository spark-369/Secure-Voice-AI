/** Rounded panel container. */
export default function Card({ className = '', children }) {
  return (
    <div className={`rounded-2xl border border-slate-800/70 bg-slate-900/40 ${className}`}>
      {children}
    </div>
  )
}
