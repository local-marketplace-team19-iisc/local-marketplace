import { useState } from 'react'
import './ProductExtractPanel.css'
import { extractProduct } from '../../services/extractService'
import { toErrorMessage } from '../../utils/helpers'
import Button from '../common/Button'
import VoiceButton from '../common/VoiceButton'
import imageGif from '../../assets/images/image.gif'

// NLP-prompt + image extraction control for the vendor add/edit form (AC-13/14, D5/D6).
// Calls onExtracted(productFields) so the parent can pre-fill the form for review.
function ProductExtractPanel({ onExtracted }) {
  const [prompt, setPrompt] = useState('')
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [done, setDone] = useState(false)

  async function run() {
    if (!prompt.trim() && !file) {
      setError('Enter a prompt or choose an image first.')
      return
    }
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
          <VoiceButton onText={(t) => setPrompt((p) => (p ? `${p} ${t}` : t))} title="Dictate product details" />
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
      </div>
    </div>
  )
}

export default ProductExtractPanel
