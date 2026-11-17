import { useCallback, useEffect, useRef, useState } from 'react'

/** Split long text into speakable chunks (mobile engines truncate long strings). */
function splitIntoChunks(text) {
  const sentences = text.replace(/\s+/g, ' ').match(/[^.!?]+[.!?]*/g) || [text]
  const chunks = []
  let current = ''
  for (const sentence of sentences) {
    if (current && (current + sentence).length > 180) {
      chunks.push(current.trim())
      current = sentence
    } else {
      current += sentence
    }
    while (current.length > 280) {
      chunks.push(current.slice(0, 280))
      current = current.slice(280)
    }
  }
  if (current.trim()) chunks.push(current.trim())
  return chunks
}

/**
 * Browser SpeechSynthesis wrapper: speaks queued sentences in order and
 * exposes a `speaking` flag so the UI can animate the "talking" state.
 */
export default function useSpeechSynthesis({ lang = 'en-US' } = {}) {
  const [supported] = useState(
    () => typeof window !== 'undefined' && 'speechSynthesis' in window,
  )
  const [speaking, setSpeaking] = useState(false)
  const voiceRef = useRef(null)

  useEffect(() => {
    if (!supported) return undefined
    const pickVoice = () => {
      const voices = window.speechSynthesis.getVoices()
      voiceRef.current =
        voices.find((voice) => voice.lang?.toLowerCase().startsWith(lang.slice(0, 2))) ||
        voices[0] ||
        null
    }
    pickVoice()
    window.speechSynthesis.onvoiceschanged = pickVoice
    return () => {
      window.speechSynthesis.onvoiceschanged = null
      window.speechSynthesis.cancel()
    }
  }, [lang, supported])

  const cancel = useCallback(() => {
    if (!supported) return
    window.speechSynthesis.cancel()
    setSpeaking(false)
  }, [supported])

  const speak = useCallback(
    (text) => {
      if (!supported || !text) return
      cancel()
      const chunks = splitIntoChunks(text)
      setSpeaking(true)
      chunks.forEach((chunk, index) => {
        const utterance = new SpeechSynthesisUtterance(chunk)
        utterance.lang = lang
        if (voiceRef.current) utterance.voice = voiceRef.current
        utterance.rate = 1
        utterance.pitch = 1
        if (index === chunks.length - 1) {
          utterance.onend = () => setSpeaking(false)
          utterance.onerror = () => setSpeaking(false)
        }
        window.speechSynthesis.speak(utterance)
      })
    },
    [cancel, lang, supported],
  )

  return { supported, speaking, speak, cancel }
}
