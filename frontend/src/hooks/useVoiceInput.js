import { useEffect, useRef, useState } from 'react'

// Voice→text via the browser Web Speech API (D9). Presentation-layer only — transcription
// is a browser capability and the resulting text flows through the normal text paths
// (C-04). Feature-detected: `supported` is false where the API is unavailable
// (e.g. Firefox), so callers can hide the mic and fall back to the always-present text box.
function getSpeechRecognition() {
  if (typeof window === 'undefined') return null
  return window.SpeechRecognition || window.webkitSpeechRecognition || null
}

export function useVoiceInput({ onResult, lang = 'en-US' } = {}) {
  const [supported] = useState(() => Boolean(getSpeechRecognition()))
  const [listening, setListening] = useState(false)
  const [error, setError] = useState(null)
  const recRef = useRef(null)
  const onResultRef = useRef(onResult)
  onResultRef.current = onResult

  useEffect(() => {
    const Ctor = getSpeechRecognition()
    if (!Ctor) return undefined
    const rec = new Ctor()
    rec.lang = lang
    rec.interimResults = false
    rec.maxAlternatives = 1
    rec.onresult = (e) => {
      const text = Array.from(e.results)
        .map((r) => r[0]?.transcript || '')
        .join(' ')
        .trim()
      if (text && onResultRef.current) onResultRef.current(text)
    }
    rec.onerror = (e) => {
      setError(e?.error || 'voice-error')
      setListening(false)
    }
    rec.onend = () => setListening(false)
    recRef.current = rec
    return () => {
      try {
        rec.abort()
      } catch {
        /* recognition already stopped */
      }
      recRef.current = null
    }
  }, [lang])

  function start() {
    if (!recRef.current || listening) return
    setError(null)
    try {
      recRef.current.start()
      setListening(true)
    } catch {
      /* start() throws if already started — ignore */
    }
  }

  function stop() {
    if (!recRef.current) return
    try {
      recRef.current.stop()
    } catch {
      /* noop */
    }
    setListening(false)
  }

  function toggle() {
    if (listening) stop()
    else start()
  }

  return { supported, listening, error, start, stop, toggle }
}
