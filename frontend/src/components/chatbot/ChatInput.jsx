import { useRef, useState } from 'react'
import Button from '../common/Button'
import VoiceButton from '../common/VoiceButton'

// Chat composer with text, voice (→text), and image attachment (AC-11, D10).
// Submits on Enter; clears text + image after send.
function ChatInput({ onSend, disabled }) {
  const [text, setText] = useState('')
  const [image, setImage] = useState(null)
  const fileRef = useRef(null)

  function submit(e) {
    e.preventDefault()
    const trimmed = text.trim()
    if (!trimmed && !image) return
    onSend(trimmed, image)
    setText('')
    setImage(null)
    if (fileRef.current) fileRef.current.value = ''
  }

  function appendVoice(t) {
    setText((prev) => (prev ? `${prev} ${t}` : t))
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
          <img src="/image.gif" alt="" aria-hidden="true" className="chat-input__attach-icon" />
        </label>

        <VoiceButton onText={appendVoice} title="Speak your message" disabled={disabled} />

        <Button type="submit" variant="primary" disabled={disabled || (!text.trim() && !image)}>Send</Button>
      </div>
    </form>
  )
}

export default ChatInput
