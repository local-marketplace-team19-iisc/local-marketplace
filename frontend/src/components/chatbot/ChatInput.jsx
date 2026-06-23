import { useRef, useState } from 'react'
import Button from '../common/Button'
import VoiceButton from '../common/VoiceButton'
import imageGif from '../../assets/images/image.gif'

// Chat composer with text, voice (→text), and image attachment (AC-11, D10).
// Submits on Enter; clears text + image after send.
//
// Voice ergonomics (feature 008 Session 6 fix, refined Session 9):
//   * If the text field is empty when voice transcription arrives, we
//     auto-submit. Voice is meant to be hands-free; making the user click
//     Send defeats the purpose.
//   * If the user had already started typing, we APPEND the transcript
//     and let them press Send — preserves the "dictate the rest of my
//     sentence" use case without surprising them.
//   * Session 9 fix: previously the auto-submit was scheduled from inside
//     a `setText(prev => …)` updater. React 18 StrictMode intentionally
//     double-invokes updater functions in development to surface impure
//     code, which scheduled the auto-submit microtask twice → two
//     `/api/chat` POSTs → duplicate product rows. The side effect now
//     lives outside the updater, gated by a `submittingRef` so any second
//     invocation (StrictMode or a fast double-toggle of the mic) is a
//     no-op.
function ChatInput({ onSend, disabled }) {
  const [text, setText] = useState('')
  const [image, setImage] = useState(null)
  const fileRef = useRef(null)
  // Single-shot guard: set true the moment a submit is dispatched, cleared
  // after the call returns. Prevents both StrictMode double-fire and
  // genuine rapid-fire double-clicks. A ref (not state) because we need
  // the latest value synchronously inside event handlers — state updates
  // are async.
  const submittingRef = useRef(false)
  const textRef = useRef('')
  textRef.current = text

  function submitWith(rawText) {
    const trimmed = (rawText ?? '').trim()
    if (!trimmed && !image) return
    if (submittingRef.current) return // dedupe re-entrant calls
    submittingRef.current = true
    try {
      onSend(trimmed, image)
    } finally {
      // Clear the guard on the next macrotask so any synchronous
      // double-invocation (StrictMode) is absorbed, but normal user
      // re-submits after the round-trip are not blocked.
      setTimeout(() => {
        submittingRef.current = false
      }, 0)
    }
    setText('')
    setImage(null)
    if (fileRef.current) fileRef.current.value = ''
  }

  function submit(e) {
    e.preventDefault()
    submitWith(textRef.current)
  }

  function appendVoice(t) {
    const incoming = (t || '').trim()
    if (!incoming) return
    if (textRef.current) {
      // User was already typing — append, don't submit.
      setText((prev) => (prev ? `${prev} ${incoming}` : incoming))
      return
    }
    // Empty field — voice owns the whole message. Submit directly with
    // the transcript. No need to round-trip through setState; submitWith
    // will clear the field anyway.
    submitWith(incoming)
  }

  return (
    <form className="chat-input" onSubmit={submit}>
      {image ? (
        <span className="chat-input__chip">
          📷 {image.name}
          <button
            type="button"
            className="chat-input__chip-x"
            aria-label="Remove image"
            onClick={() => {
              setImage(null)
              if (fileRef.current) fileRef.current.value = ''
            }}
          >
            ×
          </button>
        </span>
      ) : null}

      <div className="chat-input__row">
        <label className="visually-hidden" htmlFor="chat-text">Message the assistant</label>
        <input
          id="chat-text"
          className="chat-input__field"
          type="text"
          autoComplete="off"
          placeholder="Ask for a product…"
          value={text}
          onChange={(e) => setText(e.target.value)}
        />

        <input
          ref={fileRef}
          id="chat-image"
          className="visually-hidden"
          type="file"
          accept="image/*"
          onChange={(e) => setImage(e.target.files?.[0] || null)}
        />
        <label htmlFor="chat-image" className="chat-input__attach" title="Attach image" aria-label="Attach image">
          <img src={imageGif} alt="" aria-hidden="true" className="chat-input__attach-icon" />
        </label>

        <VoiceButton onText={appendVoice} title="Speak your message" disabled={disabled} />

        <Button type="submit" variant="primary" disabled={disabled || (!text.trim() && !image)}>Send</Button>
      </div>
    </form>
  )
}

export default ChatInput
