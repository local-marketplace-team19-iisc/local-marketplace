import { Link } from 'react-router-dom'
import './MessageBubble.css'
import { formatPrice, classNames } from '../../utils/helpers'

// Renders a single chat message. Bot replies may carry product listings returned by the
// API (AC-11), shown as quick links to the product page.
function MessageBubble({ message }) {
  const isUser = message.sender === 'user'
  return (
    <div className={classNames('bubble-row', isUser ? 'bubble-row--user' : 'bubble-row--bot')}>
      <div
        className={classNames(
          'bubble',
          isUser ? 'bubble--user' : 'bubble--bot',
          message.isError && 'bubble--error',
        )}
      >
        <p className="bubble__text">{message.text}</p>
        {message.listings && message.listings.length > 0 ? (
          <ul className="bubble__listings">
            {message.listings.map((l) => (
              <li key={l.id} className="bubble__listing">
                <Link to={`/product/${l.id}`}>{l.name}</Link>
                <span className="bubble__listing-meta">
                  {formatPrice(l.price)} · {l.vendor}
                </span>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </div>
  )
}

export default MessageBubble
