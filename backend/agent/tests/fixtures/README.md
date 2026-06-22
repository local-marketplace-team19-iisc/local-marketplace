# Test fixtures

The slow-tier tests in `tests/test_io_asr.py` and `tests/test_io_ocr.py`
look for two files here:

```
tests/fixtures/
├── sample_voice.wav        # spoken vendor sentence (5–15 s)
└── sample_image.jpg        # photo or scan of printed text
```

Both files are **git-ignored** — you produce them locally before running
the slow tests. The fast (mocked) tier in CI does not need them; it will
auto-skip with a clear message if they're missing.

---

## `sample_voice.wav`

Record a short clip (5–15 seconds) of a vendor utterance. Anything close to
the kind of sentence vendors will actually say works. Suggested phrase:

> "Add 10 kg Sona Masuri rice, 58 rupees per kilo, available in Bangalore Koramangala."

Constraints:

- Format: `.wav` (mono or stereo, any sample rate `ffmpeg` can read).
- Duration: ≤ 30 seconds (spec.md §2.2).
- Size: ≤ 10 MB.
- Clear speech, modest background noise. Whisper handles accents fine.

### Easiest recording paths on macOS

```bash
# Option A — built-in QuickTime
#   File ▸ New Audio Recording ▸ record ▸ File ▸ Export As → sample_voice.wav

# Option B — sox (if installed)
brew install sox
sox -d -c 1 -r 16000 tests/fixtures/sample_voice.wav trim 0 12

# Option C — ffmpeg with the default mic
ffmpeg -f avfoundation -i ":0" -t 12 -ac 1 -ar 16000 \
       tests/fixtures/sample_voice.wav
```

Convert any existing `.m4a` / `.mp3` to wav with:

```bash
ffmpeg -i input.m4a -ac 1 -ar 16000 tests/fixtures/sample_voice.wav
```

---

## `sample_image.jpg`

Drop a phone photo or scan of printed / clearly-written text. Suggested
content: a handwritten note or a product label like:

> "Sona Masuri Rice — 10 kg — ₹580"

Constraints:

- Format: `.jpg` (or `.png`; the test path is `sample_image.jpg`).
- Size: ≤ 5 MB.
- Reasonably in focus. Tesseract baseline does light preprocessing
  (EXIF-orient + grayscale) but no aggressive denoise / binarization.

---

## How the tests pick these up

```python
# tests/test_io_asr.py
SAMPLE_VOICE = FIXTURE_DIR / "sample_voice.wav"

@pytest.mark.slow
def test_transcribe_real_sample_voice():
    if not SAMPLE_VOICE.exists():
        pytest.skip(f"fixture missing: {SAMPLE_VOICE}")
    ...
```

Run the slow tier explicitly:

```bash
pytest -m slow                  # only slow tests
pytest -m "slow or not slow"    # everything
```

---

## Manual smoke test (without pytest)

```bash
python -m agent.io.cli transcribe tests/fixtures/sample_voice.wav
python -m agent.io.cli ocr        tests/fixtures/sample_image.jpg
```

Both commands print one JSON object on stdout. Exit codes are documented in
`agent/io/cli.py`.
