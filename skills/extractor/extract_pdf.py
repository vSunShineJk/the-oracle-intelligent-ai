from io import BytesIO

from pypdf import PdfReader


def extract_pdf(raw_bytes: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(raw_bytes))
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text.strip())

        if not pages:
            return "[PDF contains no extractable text — likely a scanned document]"

        return "\n\n".join(pages)
    except Exception as e:
        return f"[PDF extraction failed: {e}]"
