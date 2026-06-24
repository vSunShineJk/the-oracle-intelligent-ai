from io import BytesIO

from PIL import Image
import pytesseract

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def extract_image(raw_bytes: bytes) -> str:
    try:
        image = Image.open(BytesIO(raw_bytes))
        text = pytesseract.image_to_string(image, lang="eng+deu", timeout=15).strip()

        if not text:
            return "[Image contains no recognisable text]"

        return text
    except Exception as e:
        return f"[Image extraction failed: {e}]"
