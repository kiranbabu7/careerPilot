"""Resume text extraction from uploaded files."""

import logging
from io import BytesIO

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".txt", ".pdf", ".docx"}
ALLOWED_CONTENT_TYPES = {
    "text/plain",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class ExtractionError(Exception):
    pass


def get_extension(filename: str) -> str:
    if "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()


def validate_resume_file(filename: str, content_type: str, file_size: int, max_size: int) -> None:
    ext = get_extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise ExtractionError(
            f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    if file_size > max_size:
        raise ExtractionError(f"File exceeds maximum size of {max_size // (1024 * 1024)} MB.")
    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        logger.warning("Unexpected content type %s for %s", content_type, filename)


def extract_text(file_obj, filename: str) -> str:
    ext = get_extension(filename)
    if ext == ".txt":
        return _extract_txt(file_obj)
    if ext == ".pdf":
        return _extract_pdf(file_obj)
    if ext == ".docx":
        return _extract_docx(file_obj)
    raise ExtractionError(f"Unsupported file type: {ext}")


def _extract_txt(file_obj) -> str:
    raw = file_obj.read()
    if isinstance(raw, str):
        return raw.strip()
    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            return raw.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    raise ExtractionError("Could not decode text file.")


def _extract_pdf(file_obj) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ExtractionError("PDF support is not installed.") from exc

    reader = PdfReader(BytesIO(file_obj.read()))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n".join(pages).strip()
    if not text:
        raise ExtractionError("No text could be extracted from the PDF.")
    return text


def _extract_docx(file_obj) -> str:
    try:
        from docx import Document
    except ImportError as exc:
        raise ExtractionError("DOCX support is not installed.") from exc

    doc = Document(BytesIO(file_obj.read()))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    text = "\n".join(paragraphs).strip()
    if not text:
        raise ExtractionError("No text could be extracted from the DOCX file.")
    return text
