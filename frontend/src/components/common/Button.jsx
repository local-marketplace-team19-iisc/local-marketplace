import './Button.css'
import { classNames } from '../../utils/helpers'

// Reusable button. `loading` disables and shows a busy label (supports AC-03 affordances).
function Button({
  children,
  variant = 'primary',
  type = 'button',
  size = 'md',
  disabled = false,
  loading = false,
  className,
  ...rest
}) {
  return (
    <button
      type={type}
      className={classNames('btn', `btn--${variant}`, `btn--${size}`, className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? 'Please wait…' : children}
    </button>
  )
}

export default Button
