import { Component } from 'react'

/** Catches render errors and shows a recovery screen instead of a white page. */
export default class ErrorBoundary extends Component {
  state = { error: null }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('Unhandled UI error:', error, info)
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className="grid min-h-screen place-items-center bg-slate-950 px-4">
        <div className="max-w-md rounded-2xl border border-rose-500/30 bg-rose-500/5 p-6 text-center sm:p-8">
          <p className="text-3xl">💥</p>
          <h1 className="mt-3 text-lg font-semibold text-white">Something went wrong</h1>
          <p className="mt-2 text-xs text-slate-400">
            {String(this.state.error?.message || this.state.error)}
          </p>
          <button
            onClick={() => window.location.reload()}
            className="mt-5 rounded-xl bg-indigo-500 px-4 py-2 text-xs font-medium text-white hover:bg-indigo-400"
          >
            Reload the app
          </button>
        </div>
      </div>
    )
  }
}

