import { useState } from 'react'
import Button from '../common/Button'

// Chat message composer. Submits on Enter (form submit) and clears on send.
function ChatInput({ onSend, disabled }) {
  const [text, setText] = useState('')

  function submit(e) {
    e.preventDefault()
    const trimmed = text.trim()
    if (!trimmed) return
    onSend(trimmed)
    setText('')
  }

  return (
    <form className="chat-input" onSubmit={submit}>
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
      <Button type="submit" variant="primary" disabled={disabled || !text.trim()}>Send</Button>
    </form>
  )
}

export default ChatInput
