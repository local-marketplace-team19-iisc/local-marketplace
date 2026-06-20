# `agent/io/` — Input Pipeline Spec


## 1. What the input pipeline is responsible for

```
                        ┌─────────────────────────────────────────┐
HTTP / WS request ─────►│ server.py            (transport edge)   │
                        │  · authn (JWT)                          │
                        │  · multipart parsing                    │
                        │  · enforce size limits (§2.2)           │
                        │  · build RawInput                       │
                        └──────────────┬──────────────────────────┘
                                       ▼
                        ┌─────────────────────────────────────────┐
                        │ agent/orchestrator.py                   │
                        │  · loads session (Redis)                │
                        │  · classifies modality                  │
                        │  · dispatches to agent/io/              │◄── this folder owns
                        │  · wraps result as Message              │    only the modality
                        └──────────────┬──────────────────────────┘    decoders
                                       ▼
                        ┌─────────────────────────────────────────┐
                        │ agent/planner.py    (LLM brain)         │
                        └─────────────────────────────────────────┘
```

`agent/io/` owns exactly two transformations and nothing else:

| `asr.py` | **implemented** (faster-whisper) | Voice bytes → `(text, confidence, language?)` | Confidence < 0.6 ⇒ tell the caller to retry / fall back to text |
| `ocr.py` | **implemented** (pytesseract + Pillow) | Image bytes → `text` | < 3 useful characters ⇒ raise `OCRTooFewCharactersError`; never forward empty text to the LLM |
| `cli.py` | **implemented** | Manual smoke-testing: `python -m agent.io.cli transcribe|ocr <path>` → JSON | Non-zero exit code; see header docstring |

`agent/io/` **must not** call the LLM, **must not** touch the database, and **must not** touch Redis. It only knows about bytes → text. Anything else is the orchestrator's job. This is what makes [`spec.md` §2.5 architectural rule 2](../../spec.md) ("only `agent/io/*` calls Whisper or OCR") testable.


## 2. How customer and vendor provide input

Both roles share the **same** entry point. Role is a session attribute (set at login), **not** a transport detail.

### 2.1 The single HTTP entry point

```
POST /v1/agent/turn
Content-Type: multipart/form-data
Authorization: Bearer <access-jwt>
```

| `session_id` | yes | uuid (string) | issued at login, lives in an `HttpOnly` cookie or `Authorization`-bound claim |
| `text` | one of `{text, voice, image}` | utf-8 string ≤ 4 KB | typed in the chat box |
| `voice` | one of `{text, voice, image}` | `.wav` / `.m4a` ≤ 30 s ≤ 10 MB | recorded or uploaded via `VoiceUploadButton.tsx` |
| `image` | one of `{text, voice, image}` | `.jpg` / `.png` ≤ 5 MB | uploaded via `ImageUploadButton.tsx` |
| `lat`, `lng` | optional | float, float | browser `navigator.geolocation` (customer) — vendor sends it once at store creation, not per turn |

> **Rule:** exactly one of `{text, voice, image}` per turn. Two-modality turns (e.g. text + image at once) are **out of scope** in the baseline. The HTTP layer rejects them with HTTP 400 before anything reaches `agent/io/`.

### 2.2 What the **vendor** sends, in practice

Vendor onboarding (login + role pick + store creation) happens once. After that, a typical vendor turn is one of:

| Add a product | *"Add 10 kg Sona Masuri rice ₹58/kg available in Bangalore Koramangala"* | text |
| Add a product | 8-second voice clip with the same sentence | voice |
| Add a product | Photo of a handwritten note / product label | image |
| Update price | *"Change Sona Masuri price to ₹62"* | text |
| Delete product | *"Remove the IR-20 listing"* | text |
| Confirm a staged action | *"yes"* / *"confirm"* / *"go ahead"* | text (always) |

### 2.3 What the **customer** sends, in practice

| Search for a product | *"rice 10 kg near me"* | text |
| Search for a product | 5-second voice clip *"do you have basmati rice"* | voice |
| Search for a product | Photo of a shopping list | image |
| Drill into a result | *"view 1"* / *"show me store 2"* | text |
| Set / move location | *"I'm in HSR Layout"* or `(lat, lng)` from the browser | text + geo |

### 2.4 What the user **does not** do

These are deferred (see [`../../spec.md` §5.6](../../spec.md)) and the HTTP layer rejects them:

- Streaming voice (uploads a complete clip, not a live mic stream).
- Multiple files per turn.
- A modality that arrives without a session (anonymous turns ⇒ 401).
- An empty `text` field paired with no file (⇒ 400).


## 3. Next step taken after the input is received

This is the orchestrator's first 50 ms. Pseudocode of `orchestrator.handle(raw: RawInput) -> AssistantResponse`:

```python
# 1. Hard limits at the HTTP layer (server.py)
#    enforced BEFORE bytes reach this function.
#    server.py rejects with 400/413 for oversize payloads.

# 2. Build the RawInput dataclass
raw = RawInput(
    session_id=request.session_id,
    text=request.text,
    voice_bytes=request.voice.read() if request.voice else None,
    image_bytes=request.image.read() if request.image else None,
    geo=GeoPoint(lat=request.lat, lng=request.lng) if request.lat else None,
)

# 3. Load session (Redis) — needed for role + pending_action
session = memory.load(raw.session_id)
if session is None:
    return canned_reply("Your session expired. Please log in again.")

# 4. Classify modality (next section).
source = classify_modality(raw)         # "text" | "voice" | "image"

# 5. Normalise to canonical Message (next section).
message = normalise(raw, source)

# 6. From here on, the rest of the agent is modality-agnostic.
#    See AGENT_SPEC.md §5 (Planner) and §6 (Tool Catalog).
return planner.run(session, message)
```

Everything inside step 5 (`normalise`) is what this `agent/io/` package is responsible for. Steps 1–4 and step 6 are explicitly **not** this package's job.

---

## 4. How the agent decides to call OCR or ASR

> **Important:** the LLM does **not** decide which decoder to call. The decision is made by a tiny deterministic function in the orchestrator based on which multipart field the HTTP layer received. The LLM only ever sees text.

This is a deliberate safety choice:

1. The LLM is treated as untrusted (see [`../../agent-spec.md` §2.3](../../agent-spec.md)). Letting it pick decoders would let a prompt-injection payload steer routing.
2. Modality is unambiguous at the HTTP layer (we know which form-field arrived), so an LLM "decision" would just add latency and a failure mode.
3. It keeps `agent/io/` independent of the planner: the import graph stays `orchestrator → io` and `orchestrator → planner`, never `planner → io`.

### 4.1 The `classify_modality` function (deterministic)

```python
def classify_modality(raw: RawInput) -> Literal["text", "voice", "image"]:
    """Return the single modality present in `raw`.

    Invariants enforced upstream by server.py:
      - exactly one of {text, voice_bytes, image_bytes} is non-empty;
      - all size/duration limits already passed.
    """
    if raw.voice_bytes is not None:
        return "voice"
    if raw.image_bytes is not None:
        return "image"
    if raw.text:
        return "text"
    raise ValueError("RawInput has no payload — HTTP layer should have rejected this")
```

### 4.2 Dispatch table

```python
def normalise(raw: RawInput, source: str) -> Message:
    if source == "text":
        return Message(
            text=unicode_nfc(raw.text)[:4096],
            source="text",
            geo=raw.geo,
        )

    if source == "voice":
        # agent/io/asr.py — the ONLY place Whisper is invoked.
        result = transcribe_voice(raw.voice_bytes, language_hint="en")
        if result.confidence < LOW_CONFIDENCE_THRESHOLD:
            raise LowConfidenceASR(
                "Sorry, I couldn't hear that clearly. "
                "Could you try again or type it instead?"
            )
        return Message(text=result.text, source="voice", geo=raw.geo)

    if source == "image":
        # agent/io/ocr.py — the ONLY place Tesseract is invoked.
        # extract_text_from_image raises OCRTooFewCharactersError
        # if the result has < MIN_OCR_CHARS readable characters.
        result = extract_text_from_image(raw.image_bytes)
        return Message(text=result.text, source="image", geo=raw.geo)

    raise ValueError(f"unknown source: {source}")
```

### 4.3 What "decides to call OCR or ASR" really means

If someone says *"the agent decided to call OCR"*, what actually happened is:

1. The user clicked the **image upload** button in the web UI (`web/src/components/ImageUploadButton.tsx`).
2. The browser sent the file in the `image` form-field.
3. `server.py` saw a non-empty `image` field and a `Content-Type: image/*`, accepted the upload (size check), and put `image_bytes` on `RawInput`.
4. `classify_modality(raw)` returned `"image"` because `raw.image_bytes is not None`.
5. `normalise(raw, "image")` called `agent/io/ocr.extract_text_from_image(raw.image_bytes)`.

No LLM, no heuristic, no inference. The path is fully determined by which multipart field arrived.

### 4.4 What if all three fields are present (defence-in-depth)?

`server.py` should reject this with HTTP 400. If for some reason it slips through, the orchestrator picks **the most explicit** signal in this priority order: `voice > image > text`. Then it logs a `WARN: multi_modal_turn rejected` event for the SRE so we can fix the transport.

---

## 5. After ASR / OCR / text-normalisation: the handoff to the planner

Once the modality decoder finishes, every code path produces the **same** object:

```python
class Message(BaseModel):
    text:        str                                # canonical UTF-8 text
    source:      Literal["text", "voice", "image"]  # logging tag only
    geo:         GeoPoint | None = None
    attachments: list[Attachment] = []              # original blob refs (audit)
```

From this point on, **nothing downstream cares which modality the message came from**. The planner, the tools, and the formatter only see `Message.text`. The `source` tag is kept for:

- **Logs** — every turn log line carries `source=voice|image|text` so we can compute per-modality latency.
- **Metrics** — p95 latency target (`spec.md §4.4`) is split: ≤ 1.5 s for text, ≤ 3.5 s for voice / image.
- **Audit** — `attachments` keeps a reference (object-store key) to the original blob for review, never the bytes themselves.

### 5.1 What happens next, step by step

```
Message (text + source + geo?)
  │
  ▼
agent/memory.py           — append to session.history; trim to last K turns
  │
  ▼
agent/planner.py          — LLM JSON-mode call with role-specific prompt
  │                        (system_vendor.txt or system_customer.txt)
  │                        Output: PlannerOutput { thought, tool_calls[], assistant }
  │                        Validated against Pydantic schema. 1 repair attempt.
  │
  ▼
agent/tools/*             — orchestrator dispatches each tool_call:
                            · registry lookup
                            · role check (vendor/customer only sees its tools)
                            · Pydantic input validation
                            · IF tool.requires_confirmation and not already
                              confirmed → stage as pending_action and ask the
                              user "yes/confirm?" (DO NOT execute the tool)
                            · otherwise execute with timeout
  │
  ▼
PlannerOutput.assistant   — rendered as chat text + (optional) result cards
                            (e.g. search hits) by the formatter in
                            agent/orchestrator.py
  │
  ▼
HTTP response             — server.py serialises and returns to the browser
```


### 5.2 Worked example — voice → vendor add-product

```
Browser uploads voice.wav, 8s, 240 KB
   │
   ▼ POST /v1/agent/turn  (multipart: voice + session_id)
server.py
   · size OK (≤ 30s, ≤ 10 MB)
   · RawInput(voice_bytes=<bytes>, session_id=...)
   │
   ▼
orchestrator.handle()
   · classify_modality → "voice"
   · normalise() calls agent/io/asr.transcribe_voice(bytes)
       → ASRResult(text="Add 10 kg Sona Masuri rice at 58 rupees a kilo
                          available in Bangalore Koramangala",
                   confidence=0.91)
   · confidence ≥ 0.6  → build Message(text=..., source="voice")
   │
   ▼
planner.run(session={role:"vendor", ...}, message=...)
   · emits tool_calls=[extract_product_fields(free_text=...)]
   · orchestrator runs the tool (read-only, no confirmation needed)
   · planner turn 2 → tool_calls=[add_product(draft)]
   · add_product.requires_confirmation = True
       → stage pending_action; reply "Here are the fields I extracted… reply 'yes'"
   · user says "yes" (text turn)
   · planner re-emits add_product → pending_action matches → INSERT runs
```

### 5.3 Worked example — image → customer search

```
Browser uploads photo of a shopping list, 1.8 MB
   │
   ▼
server.py → RawInput(image_bytes=<bytes>)
   │
   ▼
orchestrator.handle()
   · classify_modality → "image"
   · normalise() calls agent/io/ocr.extract_text_from_image(bytes)
       → OCRResult(text="2kg rice\n1L milk\n6 eggs", char_count=23)
   · char_count ≥ 3  → Message(text="2kg rice\n1L milk\n6 eggs", source="image")
   │
   ▼
planner.run(session={role:"customer"}, message=...)
   · emits tool_calls=[search_products(text="rice", quantity=2, unit="kg",
                                        near=session.location, radius_km=5)]
   · tool returns up to 10 SearchHits, sorted by distance ASC
   · planner renders cards: "Closest matches near you: …"
```

### 5.4 Worked example — text (no decoder involved)

```
Browser POSTs text="rice 10kg near me", lat, lng
   │
   ▼
server.py → RawInput(text="rice 10kg near me", geo=GeoPoint(...))
   │
   ▼
orchestrator.handle()
   · classify_modality → "text"
   · normalise() runs Unicode NFC + 4 KB truncation. No decoder is called.
   · Message(text="rice 10kg near me", source="text", geo=...)
   │
   ▼
planner.run(...)   — identical from here on
```

---

## 6. Failure modes (what the orchestrator must surface to the user)

| voice clip silent or noisy, confidence < 0.6 | `LowConfidenceASR` | *"Sorry, I couldn't hear that clearly. Could you try again or type it?"* |
| voice clip > 30s or > 10 MB | rejected by `server.py` (413) — never reaches `agent/io/` | *"Voice messages must be ≤ 30 seconds."* |
| image with < 3 readable characters | `OCRTooFewCharactersError` | *"I couldn't read any text in that image. Could you type it instead?"* |
| image > 5 MB | rejected by `server.py` (413) | *"Images must be smaller than 5 MB."* |
| text > 4 KB | rejected by `server.py` (413) | *"That message is too long — please shorten it."* |
| text empty + no file | rejected by `server.py` (400) | (UI should disable Send) |
| multiple modalities in one turn | rejected by `server.py` (400) | (UI should disable extra inputs) |



## 7. Module contract (what other code may assume)

Anything outside `agent/io/` may rely on **exactly these**:

```python
# agent/io/__init__.py
from .asr import (
    ASRResult,
    ASRDependencyError,
    ASRPayloadTooLargeError,
    LOW_CONFIDENCE_THRESHOLD,
    transcribe_voice,
)
from .ocr import (
    OCRResult,
    OCRTooFewCharactersError,
    OCRDependencyError,
    OCRPayloadTooLargeError,
    OCRImageDecodeError,
    extract_text_from_image,
)
```

Specifically:

- `transcribe_voice(bytes, *, language_hint=None) -> ASRResult` is **pure** from the caller's POV: no DB, no network, no shared mutable state across calls (the cached Whisper model is read-only).
- `extract_text_from_image(bytes) -> OCRResult` is **pure** in the same sense; raises one of the typed exception classes on failure.
- Both functions are safe to call from a worker thread; the orchestrator may dispatch them in a `ThreadPoolExecutor` to keep the FastAPI event loop free.
- Both functions **must not** call out to network services in the baseline (Whisper + Tesseract run locally). Hosted ASR / OCR is deferred to `spec.md §5.6`.
- Both functions enforce their `max_*_bytes` cap themselves (defense-in-depth on top of the HTTP-layer 413).

---

## 8. Tests Feature-3 owns

Mirror the contract above in `tests/test_io_asr.py` and `tests/test_io_ocr.py`:

| `test_transcribe_empty_bytes_returns_low_confidence` | `transcribe_voice(b"")` → confidence 0.0 (already implemented as smoke) |
| `test_transcribe_long_clip_known_phrase` | confidence ≥ 0.6 on a fixture clip; text contains expected substring |
| `test_ocr_empty_bytes_raises` | `extract_text_from_image(b"")` raises `OCRTooFewCharactersError` (smoke) |
| `test_ocr_returns_char_count` | char_count equals `len(result.text)` on a fixture image |
| `test_ocr_min_chars_enforced` | image whose only text is "ok" (2 chars) → raises |
| `test_io_does_not_import_planner_or_tools` | static import scan: nothing in `agent/io/` imports from `agent.planner` or `agent.tools` |


---

## 9. Out of scope (don't implement here)

| Hosted ASR / OCR endpoints | `agnet-spec.md §5.6` — promote when latency budget allows |
| Streaming voice (live mic) | `agent-spec.md §5.6` |
| CLIP-style image-content understanding (recognising a product from a photo) | `agent-spec.md §5.6` |
| Multilingual / Indic language ID | `agent-spec.md §5.6` |
| TTS (text → speech reply) | `agent-spec.md §5.6` |
| File virus scanning | `server.py` / infra layer, not `agent/io/` |
| Storing the original audio / image | `server.py` writes blob to object store and passes a key, never the bytes through `agent/io/` |
