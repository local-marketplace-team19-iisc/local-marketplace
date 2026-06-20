// Convenience hook to read the Chatbot context (messages, sendMessage, session).
import { useContext } from 'react'
import { ChatbotContext } from '../store/chatbotContext'

export function useChat() {
  const ctx = useContext(ChatbotContext)
  if (!ctx) throw new Error('useChat must be used within <ChatbotProvider>.')
  return ctx
}
