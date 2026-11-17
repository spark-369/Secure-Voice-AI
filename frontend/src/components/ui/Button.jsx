/** Shared button variants (primary / outline / danger / ghost). */
const VARIANTS = {
  primary: 'bg-gradient-to-r from-indigo-500 to-cyan-500 text-white hover:brightness-110',
  solid: 'bg-indigo-500 text-white hover:bg-indigo-400',
  outline: 'border border-slate-700 text-slate-300 hover:border-slate-500 hover:text-white',
  danger: 'border border-rose-500/40 bg-rose-500/10 text-rose-200 hover:bg-rose-500/20',
  ghost: 'text-slate-400 hover:text-slate-200',
}

export default function Button({ variant = 'primary', className = '', ...props }) {
  return (
    <button
      {...props}
      className={`rounded-xl px-4 py-2 text-xs font-medium transition disabled:cursor-not-allowed disabled:opacity-40 ${
        VARIANTS[variant] || VARIANTS.primary
      } ${className}`}
    />
  )
}
