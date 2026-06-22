import './Loader.css'
import { classNames } from '../../utils/helpers'

// Loading indicator shown during API calls (AC-03). Announces politely for a11y (AC-19).
function Loader({ label = 'Loading…', inline = false, fullPage = false }) {
  return (
    <div
      className={classNames('loader', inline && 'loader--inline', fullPage && 'loader--full')}
      role="status"
      aria-live="polite"
    >
      <span className="loader__spinner" aria-hidden="true" />
      <span className={inline ? 'loader__text' : 'visually-hidden'}>{label}</span>
    </div>
  )
}

export default Loader
