"""Input normalisation adapters: modality -> text.

See `agent/io/input-spec.md` for the deep dive. Public surface:

    from backend.agent.io import transcribe_voice, extract_text_from_image
"""

from .asr import (
    ASRDependencyError,
    ASRPayloadTooLargeError,
    ASRResult,
    LOW_CONFIDENCE_THRESHOLD,
    transcribe_voice,
)
from .ocr import (
    OCRDependencyError,
    OCRImageDecodeError,
    OCRPayloadTooLargeError,
    OCRResult,
    OCRTooFewCharactersError,
    extract_text_from_image,
)

__all__ = [
    "ASRDependencyError",
    "ASRPayloadTooLargeError",
    "ASRResult",
    "LOW_CONFIDENCE_THRESHOLD",
    "OCRDependencyError",
    "OCRImageDecodeError",
    "OCRPayloadTooLargeError",
    "OCRResult",
    "OCRTooFewCharactersError",
    "extract_text_from_image",
    "transcribe_voice",
]
