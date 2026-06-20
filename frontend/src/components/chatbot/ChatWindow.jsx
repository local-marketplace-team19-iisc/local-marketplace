import { useEffect, useRef } from 'react'
import './ChatWindow.css'
import { useChat } from '../../hooks/useChat'
import MessageBubble from './MessageBubble'
import ChatInput from './ChatInput'
import Loader from '../common/Loader'

// Conversation surface. History is held in the Chatbot context for the session (AC-12);
// replies are whatever the API returns (AC-11). Auto-scrolls to the latest message.
function ChatWindow() {
  const { messages, status, sendMessage } = useChat()
  const endRef = useRef(null)
  const sending = status === 'sending'

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length, sending])

  return (
    <div className="chat-window">
      <div className="chat-window__messages" aria-live="polite">
        {messages.length === 0 ? (
          <p className="chat-window__welcome">
            👋 Hi! Tell me what you’re looking for — e.g. “fresh tomatoes” or “milk”.
          </p>
        ) : (
          messages.map((m) => <MessageBubble key={m.id} message={m} />)
        )}
        {sending ? <Loader label="Assistant is typing…" inline /> : null}
        <div ref={endRef} />
      </div>
      <ChatInput onSend={sendMessage} disabled={sending} />
    </div>
  )
}

export default ChatWindow
