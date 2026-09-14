"""Bounded text-PDF extraction in an isolated, time-limited subprocess."""

import io
import json
import sys


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
    for index, page in enumerate(reader.pages, 1):
        text = (page.extract_text() or "").strip()
        if len(text) < 10:
            raise ValueError(
                "A page has no usable text. Scanned/image PDFs need transcription; paste the verified text instead."
            )
        pages.append(f"[Source page {index}]\n{text}")
    source = "\n\n".join(pages)
    if len(source) > 6000:
        raise ValueError("This document exceeds 6,000 extracted characters. Use a shorter source.")
    return {"source": source, "pages": len(pages)}


if __name__ == "__main__":
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
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
