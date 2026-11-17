import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { useAuth } from '../../app/providers/AuthProvider.jsx'
import { api } from '../../lib/api.js'
import { SESSION_STORAGE_KEY } from '../../lib/auth.js'
import ConfirmDialog from '../../components/ui/ConfirmDialog.jsx'
import AlertBanner from './components/AlertBanner.jsx'
import MessageBubble from './components/MessageBubble.jsx'
import useSpeechRecognition from './hooks/useSpeechRecognition.js'
import useSpeechSynthesis from './hooks/useSpeechSynthesis.js'

export default function VoiceConsolePage() {
  const { user, isStaff } = useAuth()
  const navigate = useNavigate()

  const [messages, setMessages] = useState([])
  const [session, setSession] = useState(null)
  const [processing, setProcessing] = useState(false)
  const [ttsEnabled, setTtsEnabled] = useState(true)
  const [draft, setDraft] = useState('')
  const [showRename, setShowRename] = useState(false)
  const [nameDraft, setNameDraft] = useState('')
  const [activeAlert, setActiveAlert] = useState(null)
  const [bootError, setBootError] = useState(null)
  const [showJump, setShowJump] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)

  const busyRef = useRef(false)
  const sessionRef = useRef(null)
  const ttsRef = useRef(ttsEnabled)
  const scrollRef = useRef(null)

  const synthesis = useSpeechSynthesis()

  useEffect(() => {
    ttsRef.current = ttsEnabled
  }, [ttsEnabled])

  // --- session bootstrap: reuse the stored session or create a fresh one ---
  useEffect(() => {
    let cancelled = false
    const bootstrap = async () => {
      try {
        const stored = localStorage.getItem(SESSION_STORAGE_KEY)
        if (stored) {
          try {
            const detail = await api.getSession(stored)
            if (cancelled) return
            setSession(detail)
            sessionRef.current = detail.id
            setMessages(
              detail.messages.map((m) => ({
                id: `m-${m.id}`,
                role: m.role,
                content: m.content,
                createdAt: m.created_at,
                latencyMs: m.latency_ms,
              })),
            )
            return
          } catch {
            localStorage.removeItem(SESSION_STORAGE_KEY)
          }
        }
        const created = await api.createSession()
        if (cancelled) return
        setSession(created)
        sessionRef.current = created.id
        localStorage.setItem(SESSION_STORAGE_KEY, created.id)
      } catch {
        if (!cancelled) setBootError('Backend unreachable — start it with `make infra`.')
      }
    }
    bootstrap()
    return () => {
      cancelled = true
    }
  }, [])

  const refreshActiveAlert = useCallback(
    async (sessionId) => {
      // Alerts are a staff-facing surface; customers skip the poll entirely.
      if (!sessionId || !user || user.role === 'customer') return
      try {
        const alerts = await api.listAlerts({ session_id: sessionId, status: 'open', limit: 1 })
        const top = alerts?.[0]
        setActiveAlert(top && top.severity >= 0.7 ? top : null)
      } catch {
        /* ignore */
      }
    },
    [user],
  )

  const send = useCallback(
    async (text) => {
      if (!text || busyRef.current) return
      busyRef.current = true
      setProcessing(true)
      setMessages((prev) => [
        ...prev,
        {
          id: `u-${Date.now()}`,
          role: 'user',
          content: text,
          createdAt: new Date().toISOString(),
        },
      ])
      try {
        const reply = await api.sendMessage({ sessionId: sessionRef.current, text })
        if (reply.session_id && reply.session_id !== sessionRef.current) {
          sessionRef.current = reply.session_id
          setSession((prev) => (prev ? { ...prev, id: reply.session_id } : prev))
          localStorage.setItem(SESSION_STORAGE_KEY, reply.session_id)
        }
        setMessages((prev) => [
          ...prev,
          {
            id: `a-${reply.assistant_message_id}`,
            role: 'assistant',
            content: reply.reply,
            latencyMs: reply.latency_ms,
            sources: reply.sources || [],
          },
        ])
        if (ttsRef.current) synthesis.speak(reply.reply)
        await refreshActiveAlert(reply.session_id)
      } catch (err) {
        setMessages((prev) => [
          ...prev,
          {
            id: `e-${Date.now()}`,
            role: 'system',
            content: err.message || 'Connection problem — please try again.',
          },
        ])
      } finally {
        busyRef.current = false
        setProcessing(false)
      }
    },
    [refreshActiveAlert, synthesis],
  )

  const handleFinalTranscript = useCallback((text) => send(text), [send])

  const recognition = useSpeechRecognition({ onFinalResult: handleFinalTranscript })

  const toggleMic = () => {
    if (recognition.listening) {
      recognition.stop()
    } else {
      synthesis.cancel()
      recognition.start()
    }
  }

  const startNewSession = async () => {
    synthesis.cancel()
    try {
      const created = await api.createSession()
      sessionRef.current = created.id
      setSession(created)
      localStorage.setItem(SESSION_STORAGE_KEY, created.id)
      setMessages([])
      setActiveAlert(null)
    } catch {
      /* ignore */
    }
  }

  const saveRename = async () => {
    setShowRename(false)
    if (!sessionRef.current) return
    try {
      const updated = await api.updateSession(sessionRef.current, {
        customer_name: nameDraft.trim() || null,
      })
      setSession(updated)
    } catch {
      /* ignore */
    }
  }

  const deleteSession = async () => {
    synthesis.cancel()
    try {
      await api.deleteSession(sessionRef.current)
    } catch {
      /* already gone or forbidden — continue with a fresh session */
    }
    try {
      const created = await api.createSession()
      sessionRef.current = created.id
      setSession(created)
      localStorage.setItem(SESSION_STORAGE_KEY, created.id)
      setMessages([])
      setActiveAlert(null)
    } catch {
      /* ignore */
    }
    setConfirmDelete(false)
  }

  const submitDraft = (event) => {
    event.preventDefault()
    const text = draft.trim()
    if (!text) return
    setDraft('')
    send(text)
  }

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, processing])

  const handleScroll = () => {
    const el = scrollRef.current
    if (!el) return
    setShowJump(el.scrollHeight - el.scrollTop - el.clientHeight > 120)
  }

  const scrollToLatest = () => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }

  const dayLabel = (value) => {
    if (!value) return null
    const date = new Date(value)
    const today = new Date().toDateString()
    const yesterday = new Date(Date.now() - 86400000).toDateString()
    if (date.toDateString() === today) return 'Today'
    if (date.toDateString() === yesterday) return 'Yesterday'
    return date.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })
  }

  return (
    <section className="flex h-[calc(100dvh-12rem)] min-h-[420px] flex-col overflow-hidden rounded-2xl border border-slate-800/70 bg-slate-900/40 shadow-2xl shadow-black/30 sm:h-[calc(100vh-13rem)] sm:min-h-[520px] sm:rounded-3xl">
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2 border-b border-slate-800/70 px-3 py-3 sm:px-5">
        <div className="flex min-w-0 items-center gap-2 text-xs text-slate-400">
          <span className={`h-2 w-2 shrink-0 rounded-full ${session ? 'bg-emerald-400' : 'bg-slate-500'}`} />
          {showRename ? (
            <input
              autoFocus
              value={nameDraft}
              onChange={(event) => setNameDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') saveRename()
                if (event.key === 'Escape') setShowRename(false)
              }}
              onBlur={saveRename}
              placeholder="Session name"
              className="h-7 w-32 rounded-lg border border-slate-700 bg-slate-950/60 px-2 text-xs text-slate-100 placeholder:text-slate-500 focus:border-indigo-500 focus:outline-none sm:w-44"
            />
          ) : (
            <button
              onClick={() => {
                setNameDraft(session?.customer_name || '')
                setShowRename(true)
              }}
              className="truncate hover:text-slate-200"
              title="Rename session"
            >
              {session?.customer_name || `Session ${session ? session.id.slice(0, 8) : '…'}`}
            </button>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setTtsEnabled((value) => !value)}
            className={`rounded-lg border px-3 py-1.5 text-xs transition ${
              ttsEnabled
                ? 'border-indigo-500/40 bg-indigo-500/10 text-indigo-200'
                : 'border-slate-700 text-slate-400 hover:text-slate-200'
            }`}
          >
            {ttsEnabled ? '🔊' : '🔈'}
            <span className="ml-1.5 hidden sm:inline">
              {ttsEnabled ? 'Voice replies on' : 'Voice replies off'}
            </span>
          </button>
          <button
            onClick={startNewSession}
            className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-300 hover:border-slate-500 hover:text-white"
          >
            New<span className="ml-1 hidden sm:inline">session</span>
          </button>
          <button
            onClick={() => setConfirmDelete(true)}
            disabled={!session}
            className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-300 transition hover:border-rose-500/50 hover:text-rose-200 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Delete<span className="ml-1 hidden sm:inline">session</span>
          </button>
        </div>
      </div>

      {activeAlert && (
        <div className="px-5 pt-4">
          <AlertBanner
            alert={activeAlert}
            onViewDashboard={() => navigate('/dashboard')}
            onDismiss={() => setActiveAlert(null)}
          />
        </div>
      )}

      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="scrollbar-slim relative flex-1 space-y-4 overflow-y-auto px-3 py-4 sm:px-5"
      >
        {messages.length === 0 && !processing && (
          <div className="mt-10 text-center">
            <div className="mx-auto mb-4 grid h-16 w-16 place-items-center rounded-2xl bg-gradient-to-br from-indigo-500 to-cyan-500 text-3xl">
              🎙️
            </div>
            <h2 className="text-lg font-semibold text-white">Talk to SecureVoice AI</h2>
            <p className="mx-auto mt-2 max-w-md text-sm text-slate-400">
              Tap the microphone and ask about refunds, shipping, warranty or your account.
              The agent answers out loud and flags urgent issues to human agents automatically.
            </p>
          </div>
        )}
        {messages.map((message, index) => {
          const day = dayLabel(message.createdAt)
          const previous = index > 0 ? messages[index - 1].createdAt : null
          const showDay = day && (!previous || dayLabel(previous) !== day)
          return (
            <div key={message.id} className="space-y-4">
              {showDay && (
                <div className="flex justify-center">
                  <span className="rounded-full bg-slate-800/80 px-3 py-1 text-[10px] text-slate-400">
                    {day}
                  </span>
                </div>
              )}
              <MessageBubble message={message} />
            </div>
          )
        })}
        {processing && (
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <span className="h-2 w-2 animate-pulse rounded-full bg-indigo-400" />
            SecureVoice is thinking…
          </div>
        )}
        {recognition.interim && (
          <div className="rounded-2xl border border-dashed border-indigo-500/40 bg-indigo-500/5 px-4 py-3 text-sm italic text-indigo-200">
            {recognition.interim}
          </div>
        )}
        {bootError && (
          <div className="rounded-xl bg-rose-500/10 px-4 py-3 text-sm text-rose-200">{bootError}</div>
        )}
        {recognition.error && (
          <div className="rounded-xl bg-amber-500/10 px-4 py-3 text-sm text-amber-200">
            {recognition.error}
          </div>
        )}

        {showJump && (
          <button
            onClick={scrollToLatest}
            aria-label="Jump to latest message"
            className="absolute bottom-3 right-3 grid h-9 w-9 place-items-center rounded-full border border-slate-700 bg-slate-900/90 text-sm text-slate-200 shadow-lg backdrop-blur transition hover:border-indigo-500/50"
          >
            ↓
          </button>
        )}
      </div>

      {recognition.listening && (
        <div className="flex items-center gap-3 border-t border-rose-500/30 bg-rose-500/10 px-3 py-2.5 sm:px-5">
          <span className="flex h-4 items-end gap-[3px]">
            {[10, 16, 7, 14, 9].map((height, index) => (
              <span
                key={index}
                style={{ height: `${height}px`, animationDelay: `${index * 120}ms` }}
                className="w-1 animate-pulse rounded-full bg-rose-300"
              />
            ))}
          </span>
          <span className="flex-1 truncate text-xs font-medium text-rose-100">
            Listening… speak now
          </span>
          <button
            onClick={() => recognition.stop()}
            className="rounded-lg bg-rose-500 px-3 py-1 text-xs font-medium text-white transition hover:bg-rose-400"
          >
            Stop
          </button>
        </div>
      )}

      <form onSubmit={submitDraft} className="border-t border-slate-800/70 px-3 py-3 sm:px-5 sm:py-4">
        <div className="flex items-center gap-2">
          {/* Voice button — 48px circle, mirrors the send button for perfect alignment */}
          <button
            type="button"
            onClick={toggleMic}
            disabled={!recognition.supported || processing}
            aria-label={recognition.listening ? 'Stop listening' : 'Start voice input'}
            className={`relative grid h-12 w-12 shrink-0 place-items-center rounded-full text-xl transition disabled:cursor-not-allowed disabled:opacity-40 ${
              recognition.listening
                ? 'bg-rose-500 text-white'
                : 'bg-gradient-to-br from-indigo-500 to-cyan-500 text-white hover:brightness-110'
            }`}
          >
            {recognition.listening && (
              <span className="absolute inset-0 animate-pulse-ring rounded-full bg-rose-500/60" />
            )}
            <span className="relative">{recognition.listening ? '⏹' : '🎙️'}</span>
          </button>

          {/* Message input pill */}
          <input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder={
              recognition.supported ? 'Message…' : 'Voice input needs Chrome/Edge — type here…'
            }
            aria-label="Type a message"
            className="h-12 min-w-0 flex-1 rounded-full border border-slate-700 bg-slate-950/60 px-4 text-sm text-slate-100 placeholder:text-slate-500 focus:border-indigo-500 focus:outline-none"
          />

          {/* Send button — 48px circle: dimmed when empty, gradient when ready */}
          <button
            type="submit"
            disabled={processing || !draft.trim()}
            aria-label="Send message"
            className={`grid h-12 w-12 shrink-0 place-items-center rounded-full text-lg transition ${
              draft.trim() && !processing
                ? 'bg-indigo-500 text-white hover:bg-indigo-400'
                : 'bg-slate-800 text-slate-500'
            }`}
          >
            ➤
          </button>
        </div>
        <p className="mt-2 text-center text-[11px] text-slate-500">
          Your speech is transcribed in your browser — only the recognised text is sent to the
          server.
        </p>
      </form>

      <ConfirmDialog
        open={confirmDelete}
        title="Delete this session?"
        message="The full transcript will be permanently removed. A fresh session will start right afterwards."
        confirmLabel="Delete session"
        busy={processing}
        onConfirm={deleteSession}
        onCancel={() => setConfirmDelete(false)}
      />
    </section>
  )
}


