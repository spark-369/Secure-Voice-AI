/** Shared text input / textarea styles. */
export const inputClass =
  'w-full rounded-xl border border-slate-700 bg-slate-950/60 px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-500 focus:border-indigo-500 focus:outline-none'

export default function Input({ className = '', ...props }) {
  return <input {...props} className={`${inputClass} ${className}`} />
}

export function Textarea({ className = '', ...props }) {
  return <textarea {...props} className={`${inputClass} ${className}`} />
}
