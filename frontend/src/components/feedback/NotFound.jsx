import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="grid min-h-screen place-items-center bg-slate-950 px-4">
      <div className="text-center">
        <p className="text-5xl">🧭</p>
        <h1 className="mt-4 text-2xl font-semibold text-white">Page not found</h1>
        <p className="mt-2 text-sm text-slate-400">That route does not exist.</p>
        <Link
          to="/"
          className="mt-6 inline-block rounded-xl bg-indigo-500 px-4 py-2 text-xs font-medium text-white hover:bg-indigo-400"
        >
          Back to the voice console
        </Link>
      </div>
    </div>
  )
}
