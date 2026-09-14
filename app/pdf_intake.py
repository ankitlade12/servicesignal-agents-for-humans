"""Bounded text-PDF extraction in an isolated, time-limited subprocess."""

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def ocr_page(raw, index):
    if os.getenv("PDF_OCR_ENABLED", "1") != "1" or not shutil.which("tesseract"):
        raise ValueError(
            "A page has no usable text. Enable the installed OCR engine or paste a verified transcription."
        )
    import pypdfium2 as pdfium

    with pdfium.PdfDocument(raw) as document:
        page = document[index]
        width, height = page.get_size()
        scale = min(2.5, (12_000_000 / max(1, width * height)) ** 0.5)
        if scale < 0.5:
            raise ValueError("This scanned page is too large to read safely.")
        bitmap = page.render(scale=scale)
        with tempfile.TemporaryDirectory(prefix="servicesignal-ocr-") as folder:
            image = Path(folder) / "page.png"
            bitmap.to_pil().save(image)
            result = subprocess.run(
                ["tesseract", str(image), "stdout", "-l", "eng", "--psm", "3"],
                capture_output=True,
                timeout=12,
                check=True,
                env={**os.environ, "OMP_THREAD_LIMIT": "1"},
            )
        bitmap.close()
        page.close()
    return result.stdout.decode("utf-8").strip()


def extract(raw):
    from pypdf import PdfReader

    if not raw.startswith(b"%PDF-"):
        raise ValueError("Upload a text-based PDF file.")
    reader = PdfReader(io.BytesIO(raw), strict=True)
    if reader.is_encrypted:
        raise ValueError("Password-protected PDFs are unsupported. Paste the message instead.")
    if not 1 <= len(reader.pages) <= 3:
        raise ValueError("Upload a PDF containing one to three pages.")
    pages = []
    ocr_pages = []
    for index, page in enumerate(reader.pages, 1):
        text = (page.extract_text() or "").strip()
        if len(text) < 10:
            text = ocr_page(raw, index - 1)
            ocr_pages.append(index)
            if len(text) < 10:
                raise ValueError("A page has no usable text after OCR. Paste a verified transcription.")
        pages.append(f"[Source page {index}]\n{text}")
    source = "\n\n".join(pages)
    if len(source) > 6000:
        raise ValueError("This document exceeds 6,000 extracted characters. Use a shorter source.")
    return {"source": source, "pages": len(pages), "ocr_pages": ocr_pages}


if __name__ == "__main__":
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
        if sys.platform == "linux":
            resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
        raw = sys.stdin.buffer.read(5 * 1024**2 + 1)
        if len(raw) > 5 * 1024**2:
            raise ValueError("PDFs must be no larger than 5 MB.")
        print(json.dumps(extract(raw)))
    except Exception as error:
        message = (
            str(error)
            if isinstance(error, ValueError)
            else "This PDF could not be read. Paste its verified text instead."
        )
        print(json.dumps({"error": message}))
        sys.exit(1)
