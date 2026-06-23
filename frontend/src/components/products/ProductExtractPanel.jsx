import { useRef, useState } from 'react'
import './ProductExtractPanel.css'
import { extractProduct } from '../../services/extractService'
import { toErrorMessage } from '../../utils/helpers'
import Button from '../common/Button'
import VoiceButton from '../common/VoiceButton'
import imageGif from '../../assets/images/image.gif'

// NLP-prompt + image extraction control for the vendor add/edit form (AC-13/14, D5/D6).
// Calls onExtracted(productFields) so the parent can pre-fill the form for review.
// When `onCreateFromDescription` is provided, also offers a direct
// "Create from description" action that sends the typed/spoken text to the
// SBERT chat router with an explicit `add_product` intent hint (session 9),
// skipping the manual form.
//
// Voice ergonomics (session 10): mirrors the chatbot ChatInput behaviour.
// If the prompt textarea is empty when the voice transcript arrives, we
// auto-submit through `createDirect` so the vendor's hands-free flow
// completes without a manual click. If the user had already typed
// something, we APPEND the transcript and let them press the button —
// preserves the "dictate the rest of my sentence" use case.
function ProductExtractPanel({ onExtracted, onCreateFromDescription }) {
  const [prompt, setPrompt] = useState('')
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState(null)
  const [done, setDone] = useState(false)
  // Ref-based single-shot guards. The Button component already sets
  // `disabled` while `loading`/`creating` is true, but React 18 StrictMode
  // double-invokes event handlers in development. A ref lets us short-
  // circuit any second synchronous invocation before it can issue a
  // duplicate API call.
  const runningRef = useRef(false)
  const creatingRef = useRef(false)
  // Sync mirror of `prompt` so the voice handler can read the latest
  // value without a stale closure (state updates are async).
  const promptRef = useRef('')
  promptRef.current = prompt

  async function run() {
    if (!prompt.trim() && !file) {
      setError('Enter a prompt or choose an image first.')
      return
    }
    if (runningRef.current) return
    runningRef.current = true
    setLoading(true)
    setError(null)
    setDone(false)
    try {
      const { product } = await extractProduct({ prompt: prompt.trim() || undefined, image: file || undefined })
      onExtracted(product)
      setDone(true)
    } catch (err) {
      setError(toErrorMessage(err))
    } finally {
      setLoading(false)
      runningRef.current = false
    }
  }

  // Direct create via the SBERT chat router. Accepts an optional explicit
  // text so the voice path can supply the transcript synchronously
  // without waiting for `setPrompt` to flush (avoids race + stale-closure
  // bugs). Only treat the argument as text when it is actually a string —
  // React onClick handlers pass a synthetic event object, which we must
  // ignore so we fall back to `promptRef.current`.
  async function createDirect(explicitText) {
    const explicit = typeof explicitText === 'string' ? explicitText : ''
    const text = (explicit || promptRef.current || '').trim()
    if (!text) {
      setError('Describe the product first.')
      return
    }
    if (creatingRef.current) return
    creatingRef.current = true
    setCreating(true)
    setError(null)
    setDone(false)
    try {
      await onCreateFromDescription(text)
      setPrompt('')
    } catch (err) {
      setError(toErrorMessage(err))
    } finally {
      setCreating(false)
      creatingRef.current = false
    }
  }

  // Voice transcript handler. Mirrors ChatInput.appendVoice: empty
  // textarea → auto-submit; non-empty → append. Side effect lives
  // OUTSIDE the setState updater so React 18 StrictMode's double-invoke
  // of updaters cannot schedule two API calls (session 9 lesson).
  function appendVoice(t) {
    const incoming = (t || '').trim()
    if (!incoming) return
    if (promptRef.current.trim()) {
      // User had already typed — append, don't auto-submit.
      setPrompt((p) => (p ? `${p} ${incoming}` : incoming))
      return
    }
    // Empty textarea — voice owns the whole description. Reflect it in
    // the UI so the vendor sees what was captured, then auto-submit
    // with the transcript directly (no wait for state).
    setPrompt(incoming)
    if (onCreateFromDescription) {
      createDirect(incoming)
    }
  }

  return (
    <div className="extract-panel">
      <p className="extract-panel__title">✨ Auto-fill from a prompt or image</p>
      <div className="form-group">
        <label className="form-label" htmlFor="extract-prompt">Describe the product</label>
        <div className="extract-panel__prompt">
          <textarea
            id="extract-prompt"
            className="form-textarea"
            placeholder="e.g. Amul butter 100g, ₹58, 30 in stock, Dairy"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
          />
          <VoiceButton onText={appendVoice} title="Dictate product details — auto-submits when complete" />
        </div>
      </div>
      <div className="form-group">
        <label className="form-label" htmlFor="extract-image">
          <img src={imageGif} alt="" aria-hidden="true" className="icon-gif" /> …or upload a product image
        </label>
        <input
          id="extract-image"
          className="form-input"
          type="file"
          accept="image/*"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
        />
      </div>
      {error ? <span className="form-error">{error}</span> : null}
      {done ? <span className="form-hint">Fields filled below — review and save.</span> : null}
      <div className="extract-panel__action">
        <Button type="button" variant="secondary" onClick={run} loading={loading}>Auto-fill fields</Button>
        {onCreateFromDescription ? (
          <Button type="button" variant="primary" onClick={createDirect} loading={creating} disabled={!prompt.trim()}>
            Create from description
          </Button>
        ) : null}
      </div>
    </div>
  )
}

export default ProductExtractPanel
