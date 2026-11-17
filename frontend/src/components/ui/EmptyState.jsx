/** Friendly empty-state block. */
export default function EmptyState({ icon = '📭', title, hint }) {
  return (
    <div className="rounded-2xl border border-dashed border-slate-700 px-6 py-16 text-center">
      <p className="text-3xl">{icon}</p>
      <p className="mt-3 text-sm font-medium text-slate-300">{title}</p>
      {hint && <p className="mx-auto mt-1 max-w-md text-xs text-slate-500">{hint}</p>}
    </div>
  )
}
