import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Browser SpeechRecognition wrapper (Chrome / Edge / Safari 14.1+).
 *
 * Push-to-talk style: one utterance per `start()`; the recognised final text
 * is delivered through the `onFinalResult` callback. Interim results are
 * exposed for live captioning while the customer is speaking.
 */
export default function useSpeechRecognition({ lang = 'en-US', onFinalResult } = {}) {
  const recognitionRef = useRef(null)
  const onFinalRef = useRef(onFinalResult)
  const startingRef = useRef(false)

  const [supported] = useState(
    () =>
      typeof window !== 'undefined' &&
      !!(window.SpeechRecognition || window.webkitSpeechRecognition),
  )
  const [listening, setListening] = useState(false)
  const [interim, setInterim] = useState('')
  const [error, setError] = useState(null)

  useEffect(() => {
    onFinalRef.current = onFinalResult
  }, [onFinalResult])

  useEffect(() => {
    if (!supported) return undefined
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    const recognition = new SpeechRecognition()
    recognition.continuous = false
    recognition.interimResults = true
    recognition.lang = lang
    recognition.maxAlternatives = 1

    recognition.onresult = (event) => {
      let interimText = ''
      let finalText = ''
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i]
        if (result.isFinal) finalText += result[0].transcript
        else interimText += result[0].transcript
      }
      if (interimText) setInterim(interimText)
      if (finalText.trim()) {
        setInterim('')
        onFinalRef.current?.(finalText.trim())
      }
    }
    recognition.onerror = (event) => {
      setError(
        event.error === 'not-allowed'
          ? 'Microphone permission denied — allow mic access and retry.'
          : `Speech recognition error: ${event.error}`,
      )
      setListening(false)
      startingRef.current = false
    }
    recognition.onend = () => {
      setListening(false)
      setInterim('')
      startingRef.current = false
    }

    recognitionRef.current = recognition
    return () => {
      recognition.onresult = null
      recognition.onerror = null
      recognition.onend = null
      try {
        recognition.abort()
      } catch {
        /* already stopped */
      }
      recognitionRef.current = null
    }
  }, [lang, supported])

  const start = useCallback(() => {
    if (!recognitionRef.current || listening || startingRef.current) return
    setError(null)
    startingRef.current = true
    try {
      recognitionRef.current.start()
      setListening(true)
    } catch {
      // start() throws when the engine is already running — safe to ignore.
      startingRef.current = false
    }
  }, [listening])

  const stop = useCallback(() => {
    if (!recognitionRef.current) return
    try {
      recognitionRef.current.stop()
    } catch {
      /* ignore */
    }
    setListening(false)
  }, [])

  const clearError = useCallback(() => setError(null), [])

  return { supported, listening, interim, error, start, stop, clearError }
}
