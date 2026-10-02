import io, re, os, hashlib
from pathlib import Path
from datetime import datetime
from PIL import Image
import fitz
from docx import Document as DocxDocument
from .config import settings

def extract_document(data:bytes, filename:str):
    if not data:
        raise ValueError("Document is empty.")
    ext=Path(filename).suffix.lower()
    pages=[]; method="text"
    if ext==".pdf":
        doc=fitz.open(stream=data,filetype="pdf")
        for i,page in enumerate(doc):
            text=page.get_text("text").strip()
            if not text and settings.ocr_enabled:
                method="ocr"
                pix=page.get_pixmap(matrix=fitz.Matrix(2,2),alpha=False)
                img=Image.open(io.BytesIO(pix.tobytes("png")))
                try:
                    import pytesseract
                    if settings.tesseract_cmd: pytesseract.pytesseract.tesseract_cmd=settings.tesseract_cmd
                    text=pytesseract.image_to_string(img)
                except Exception as e:
                    raise RuntimeError("OCR is required for scanned pages. Install Tesseract and configure TESSERACT_CMD.") from e
            pages.append((i+1,text))
        if not any(text.strip() for _, text in pages):
            raise ValueError("No text could be extracted from the PDF. Enable OCR for scanned documents.")
        return pages, method, len(doc)
    if ext==".docx":
        d=DocxDocument(io.BytesIO(data)); text="\n".join(p.text for p in d.paragraphs)
        if not text.strip():
            raise ValueError("DOCX document contains no extractable text.")
        return [(1,text)],"docx",1
    if ext==".txt":
        text=data.decode("utf-8",errors="replace")
        if not text.strip():
            raise ValueError("TXT document is empty.")
        return [(1,text)],"text",1
    if ext in {".png",".jpg",".jpeg",".webp"}:
        if not settings.ocr_enabled: raise RuntimeError("OCR is disabled")
        try:
            import pytesseract
            if settings.tesseract_cmd: pytesseract.pytesseract.tesseract_cmd=settings.tesseract_cmd
            text=pytesseract.image_to_string(Image.open(io.BytesIO(data)))
            if not text.strip():
                raise ValueError("OCR completed but produced no text.")
            return [(1,text)],"ocr",1
        except Exception as e: raise RuntimeError("Image OCR failed. Install Tesseract.") from e
    raise RuntimeError("Unsupported file type")

def chunk_pages(pages,chunk_size=900,overlap=120):
    chunks=[]
    for page,text in pages:
        text=re.sub(r"\s+"," ",text).strip()
        if not text: continue
        start=0
        while start<len(text):
            end=min(len(text),start+chunk_size)
            piece=text[start:end].strip()
            if piece: chunks.append((page,piece))
            if end>=len(text): break
            start=max(start+1,end-overlap)
    return chunks

def infer_metadata(filename: str, text: str = ""):
    """Infer safe policy metadata from filename/document text when upload metadata is omitted."""
    blob = f"{filename}\n{text[:12000]}"
    version = None
    m = re.search(r"(?:version|v)[\s:_-]*(20\d{2}|[A-Z])\b", blob, re.I)
    if m:
        version = m.group(1).upper()
    if not version:
        m = re.search(r"\b(20\d{2})\b", filename)
        if m:
            version = m.group(1)
    effective = parse_date(blob)
    supersedes = None
    m = re.search(r"supersedes?\s+(?:the\s+)?(?:.*?\b)(20\d{2})", blob, re.I)
    if m:
        supersedes = m.group(1)
    return {"version": version or "unversioned", "effective_date": effective, "supersedes_year": supersedes, "metadata_uncertain": not bool(version and effective)}


def parse_date(text):
    if not text:return None
    m=re.search(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})",text)
    if m:return f"{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m=re.search(r"(20\d{2})",text)
    return f"{m.group(1)}-01-01" if m else None
