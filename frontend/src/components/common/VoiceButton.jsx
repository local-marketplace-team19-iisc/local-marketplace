import './VoiceButton.css'
import { useVoiceInput } from '../../hooks/useVoiceInput'
import { classNames } from '../../utils/helpers'
import micGif from '../../assets/images/ai-microphone.gif'

// Mic toggle that feeds transcribed text to `onText`. Renders nothing where the Web
// Speech API is unsupported (graceful degradation — the text input always remains).
function VoiceButton({ onText, title = 'Speak', disabled = false }) {
  const { supported, listening, toggle } = useVoiceInput({ onResult: onText })
  if (!supported) return null
  return (
    <button
      type="button"
      className={classNames('voice-btn', listening && 'voice-btn--on')}
      onClick={toggle}
      disabled={disabled}
      aria-pressed={listening}
      aria-label={listening ? 'Stop voice input' : title}
      title={listening ? 'Listening… click to stop' : title}
    >
      <img src={micGif} alt="" aria-hidden="true" className="voice-btn__icon" />
    </button>
  )
}

export default VoiceButton
