from __future__ import annotations

import io

import pytesseract
from PIL import Image
from pytesseract import Output


def is_image_content_type(content_type: str) -> bool:
    return content_type in {
        "image/png",
        "image/jpeg",
        "image/jpg",
        "image/webp",
    }


def extract_text_from_image(data: bytes, *, langs: str = "eng+spa") -> tuple[str, float]:
    try:
        with Image.open(io.BytesIO(data)) as image:
            text = pytesseract.image_to_string(image, lang=langs, config="--psm 6")
            details = pytesseract.image_to_data(image, lang=langs, output_type=Output.DICT)
    except (pytesseract.TesseractError, OSError):
        return "", 0.0

    confidences: list[float] = []
    for raw_confidence in details.get("conf", []):
        try:
            confidence = float(raw_confidence)
        except (TypeError, ValueError):
            continue
        if confidence >= 0:
            confidences.append(confidence)

    average_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    return text, average_confidence
