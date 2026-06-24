from skills.extractor.extract_pdf import extract_pdf
from skills.extractor.extract_image import extract_image


def extract_text(filename: str, raw_bytes: bytes, mime_type: str) -> str:
    if mime_type == "application/pdf":
        return extract_pdf(raw_bytes)
    if mime_type in ("image/jpeg", "image/jpg", "image/png"):
        return extract_image(raw_bytes)
    return f"[Unsupported file type: {mime_type}]"
