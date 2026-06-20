import ChatWindow from '../components/chatbot/ChatWindow'

// Conversational search page (AC-11/12). The chat UI is fully driven by the Chatbot
// context and chatbot service.
function ChatbotPage() {
  return (
    <div className="container">
      <h1 className="page-title">Marketplace assistant</h1>
      <ChatWindow />
    </div>
  )
}

export default ChatbotPage
