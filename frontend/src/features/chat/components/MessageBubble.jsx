import { useState } from 'react'

import { formatTime } from '../../../lib/format.js'

export default function MessageBubble({ message }) {
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(message.content)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      /* clipboard unavailable */
    }
  }

  if (message.role === 'system') {
    return (
      <div className="mx-auto max-w-md rounded-xl bg-rose-500/10 px-4 py-2 text-center text-xs text-rose-200">
        {message.content}
      </div>
    )
  }

  const isUser = message.role === 'user'
  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`}>
      <div
        className={`grid h-8 w-8 shrink-0 place-items-center rounded-xl text-[10px] font-bold ${
          isUser
            ? 'bg-slate-700 text-slate-200'
            : 'bg-gradient-to-br from-indigo-500 to-cyan-500 text-white'
        }`}
      >
        {isUser ? 'YOU' : 'SV'}
      </div>
      <div className={`flex max-w-[85%] flex-col gap-1 sm:max-w-[75%] ${isUser ? 'items-end' : ''}`}>
        <div
          className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
            isUser
              ? 'rounded-tr-sm bg-indigo-500/90 text-white'
              : 'rounded-tl-sm border border-slate-700/70 bg-slate-800/60 text-slate-100'
          }`}
        >
          {message.content}
        </div>
        {!isUser && message.sources?.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {message.sources.map((source, index) => (
              <span
                key={`${source.document_id}-${source.chunk_index}-${index}`}
                title={source.snippet}
                className="rounded-full border border-slate-700 bg-slate-900/70 px-2 py-0.5 text-[10px] text-slate-400"
              >
                📚 {source.title || 'doc'} #{source.chunk_index}
              </span>
            ))}
          </div>
        )}
        <span className="flex items-center gap-1.5 px-1 text-[10px] text-slate-500">
          {formatTime(message.createdAt)}
          {message.latencyMs != null ? ` · ${message.latencyMs} ms` : ''}
          <button onClick={copy} title="Copy message" className="rounded px-1 hover:text-slate-300">
            {copied ? '✓' : '⧉'}
          </button>
        </span>
      </div>
    </div>
  )
}

