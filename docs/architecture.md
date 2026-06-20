# Architecture Decision Log — Local Marketplace

Living decision log (SPEC §4 / §8). Filled incrementally per feature; append-only —
never pre-populated, never truncated. Newest entries appended below.

---

## Feature 002 — Frontend (2026-06-18)

React presentation layer (`frontend/` slice). Decisions:

- **D1 — React 19+** for the frontend (feature spec C-01).
  - ⚠️ **Conflict with master `SPEC.md` §5**, which states "React 18". This entry is the
    record of that divergence. Resolution requires a **human PR** to update `SPEC.md` §5
    (AI is forbidden from editing `SPEC.md`/root `CLAUDE.md` per Constitution P5). Until
    reconciled, `SPEC.md` §5 and this feature disagree by design/decision.
- **D2 — State management: React Context API + `useReducer`** (C-02). The `src/store/`
  folder is retained but contains Context providers/reducers, not Redux slices. No Redux
  dependency is introduced.
- **D3 — Backend integration via a mocked, assumed REST contract.** The backend
  currently exposes only `GET /health`; no `docs/api/openapi.json` exists. The frontend
  service layer is toggled by `VITE_USE_MOCKS` and points at `VITE_API_BASE_URL`. The
  assumed contract is documented in `specs/002-frontend/spec.md` §6 and
  `frontend/FRONTEND_DOCUMENTATION.md` §4. When the backend publishes real endpoints, flip
  the toggle/base URL — no UI changes required.
- **Build tooling — Vite** (React 19; CRA deprecated). Consequence: `index.html` lives
  at the `frontend/` root (Vite convention), deviating from the input spec's
  `public/index.html` drawing. `public/` holds static assets.
- **Auth/token handling — JWT in memory only** (Constitution-aligned with C-09: no
  sensitive data in browser storage). Session is lost on refresh; the production target
  is an httpOnly cookie issued by the backend, deferred to the auth/backend feature.

Open items (tracked in `specs/002-frontend/spec.md` §7): backend endpoint confirmation,
optional UI component library, and whether `TEST_CASES` must be a true `.xlsx`.

### Feature 002 — Frontend: NLP & image input (spec revision 2026-06-19)

The feature owner updated AC-09/13/14/15 to require NLP-prompt and image-based input.
Decisions:

- **D5 — NLP/image via mocked extraction.** Frontend adds NLP-prompt + image-upload UI;
  extraction/search is mocked behind `VITE_USE_MOCKS` (extends D3). New assumed endpoints:
  `POST /api/search/image` and `POST /api/extract/product` (both `multipart/form-data`).
  The mock derives fields heuristically from prompt text / image filename — **not real
  vision** — for flow demonstration; real NLP/vision wired later by flipping the toggle.
- **D6 — Vendor add/update flow:** extraction **pre-fills the form for review then save**
  (keeps AC-05 validation), rather than writing "directly to inventory" unattended.
- **D7 — Delete (AC-15)** stays a normal button + confirmation action.
- **D8 — Customer search (AC-09)** gains image upload → matched products, alongside the
  existing text/NLP query.
- ⚠️ **Image input is beyond master `SPEC.md`** (text + voice→text later; no images).
  Recorded here as a divergence; **requires a human PR** to update `SPEC.md` (AI does not
  edit it, P5).

### Feature 002 — Frontend: Voice input + chatbot media + voice delete (spec revision 2026-06-19b)

AC-09/11/13/14/15 revised again to add voice input; AC-11 chatbot to accept voice/text/image.

- **D9 — Voice via browser Web Speech API** (`SpeechRecognition`/`webkitSpeechRecognition`).
  Reusable `useVoiceInput` hook + `VoiceButton`, reused in search, chatbot, vendor extract,
  and voice-delete. Voice→text only (transcription client-side); the resulting text flows
  through existing text endpoints. Mic hidden/disabled where unsupported (Firefox, older
  Safari) — graceful degradation for AC-06. **Aligns with master `SPEC.md` §2** ("voice→text
  later") — not a divergence (unlike image).
- **D10 — Chatbot media:** chat input adds mic + image attach; image sent to `POST /api/chat`
  (multipart) → reply + listings (mock derives from filename).
- **D11 — Voice/NLP delete (AC-15):** a voice/text prompt names the product; the frontend
  matches it among the vendor's own products and opens the existing delete confirmation.
  Supersedes D7 ("normal delete only"); confirmation retained for safety.
- Browser-automation note: Web Speech API needs a real mic + can't run in headless
  automation, so speech itself is verified manually; the text-equivalent paths (typed
  prompt, image attach, typed delete prompt) and the mic's supported/disabled gating are
  automatable.
