// Chatbot state via Context + useReducer (D2). Conversation history is kept in memory
// for the lifetime of the mounted app, so it persists across the session (AC-12).

import { createContext, useReducer, useState } from 'react'
import * as chatbotService from '../services/chatbotService'
import { toErrorMessage, uid } from '../utils/helpers'

const initialState = { messages: [], status: 'idle', error: null }

function reducer(state, action) {
  switch (action.type) {
    case 'ADD_MESSAGE':
      return { ...state, messages: [...state.messages, action.message] }
    case 'SENDING':
      return { ...state, status: 'sending', error: null }
    case 'DONE':
      return { ...state, status: 'idle' }
    case 'ERROR':
      return { ...state, status: 'error', error: action.error }
    case 'RESET':
      return { ...initialState }
    default:
      return state
  }
}

export const ChatbotContext = createContext(null)

export function ChatbotProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, initialState)
  const [sessionId] = useState(() => uid('session'))

  async function sendMessage(text) {
    const trimmed = (text || '').trim()
    if (!trimmed) return
    dispatch({ type: 'ADD_MESSAGE', message: { id: uid('msg'), sender: 'user', text: trimmed } })
    dispatch({ type: 'SENDING' })
    try {
      const { reply, listings } = await chatbotService.sendChat(trimmed, sessionId)
      dispatch({
        type: 'ADD_MESSAGE',
        message: { id: uid('msg'), sender: 'bot', text: reply, listings: listings || [] },
      })
      dispatch({ type: 'DONE' })
    } catch (err) {
      const error = toErrorMessage(err)
      dispatch({ type: 'ADD_MESSAGE', message: { id: uid('msg'), sender: 'bot', text: error, isError: true } })
      dispatch({ type: 'ERROR', error })
    }
  }

  const reset = () => dispatch({ type: 'RESET' })

  const value = {
    messages: state.messages,
    status: state.status,
    error: state.error,
    sessionId,
    sendMessage,
    reset,
  }

  return <ChatbotContext.Provider value={value}>{children}</ChatbotContext.Provider>
}
