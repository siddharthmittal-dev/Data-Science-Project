"""Stream pages from an operator-reviewed document directory."""

import subprocess
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path

FORMATS = {".pdf", ".png", ".jpg", ".jpeg", ".txt"}
MAX_FILES = 30
MAX_BYTES = 12 * 1024 * 1024
MAX_PAGES = 50
MAX_PAGE_TEXT = 30_000
CHUNK_SIZE = 900
OVERLAP = 120


def _unsafe_path(path: Path) -> bool:
    return path.is_symlink() or path.is_junction()


def directory_files(root: Path) -> Iterator[Path]:
    if not root.is_dir() or _unsafe_path(root):
        raise ValueError("Choose a regular directory of approved documents.")
    count = 0
    for folder, directories, names in root.walk():
        directories[:] = sorted(
            name for name in directories if not name.startswith(".") and not _unsafe_path(folder / name)
        )
        for name in sorted(names):
            path = folder / name
            if name.startswith(".") or path.suffix.lower() not in FORMATS or _unsafe_path(path):
                continue
            if not path.is_file():
                continue
            count += 1
            if count > MAX_FILES:
                raise ValueError(f"Corpus is limited to {MAX_FILES} files.")
            yield path


def _ocr(image, executable: str, language: str) -> str:
    """Sparse-text recognition for scans, signs, and printed map labels."""
    image.thumbnail((2800, 2800))
    with BytesIO() as png:
        image.convert("RGB").save(png, format="PNG")
        try:
            result = subprocess.run(
                [executable, "stdin", "stdout", "-l", language, "--psm", "11"],
                input=png.getvalue(), capture_output=True, check=True, timeout=30,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ValueError("OCR failed. Verify Tesseract and the selected language pack.") from exc
    return result.stdout.decode("utf-8")


def _pdf_pages(data: bytes, executable: str, language: str, force_ocr: bool) -> Iterator[tuple[int, str]]:
    import pypdfium2 as pdfium

    with pdfium.PdfDocument(data) as pdf:
        if len(pdf) > MAX_PAGES:
            raise ValueError(f"PDF exceeds {MAX_PAGES} pages.")
        for index in range(len(pdf)):
            page = pdf[index]
            try:
                text_page = page.get_textpage()
                try:
                    text = text_page.get_text_bounded().strip()
                finally:
                    text_page.close()
                if force_ocr or not text:
                    scale = min(3.0, 2800 / max(page.get_size()))
                    bitmap = page.render(scale=scale, fill_color=(255, 255, 255, 255))
                    try:
                        scanned = _ocr(bitmap.to_pil().copy(), executable, language)
                    finally:
                        bitmap.close()
                    text = scanned.strip() or text
            finally:
                page.close()
            yield index + 1, text


def read_document(path: Path) -> bytes:
    with path.open("rb") as source:
        data = source.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("Document exceeds 12 MiB.")
    return data


def load_pages(path: Path, executable: str = "tesseract", language: str = "eng",
               force_ocr: bool = False) -> Iterator[tuple[int, str]]:
    yield from load_document_pages(read_document(path), path.suffix, executable, language, force_ocr)


def load_document_pages(data: bytes, extension: str, executable: str = "tesseract",
                        language: str = "eng", force_ocr: bool = False) -> Iterator[tuple[int, str]]:
    if len(data) > MAX_BYTES:
        raise ValueError("Document exceeds 12 MiB.")
    extension = extension.lower()
    if extension not in FORMATS:
        raise ValueError("Unsupported document format.")
    if extension == ".txt":
        yield 1, data.decode("utf-8-sig")
    elif extension == ".pdf":
        if not data.startswith(b"%PDF-"):
            raise ValueError("Invalid PDF header.")
        yield from _pdf_pages(data, executable, language, force_ocr)
    elif extension in {".png", ".jpg", ".jpeg"}:
        from PIL import Image, ImageOps

        with Image.open(BytesIO(data), formats=["PNG", "JPEG"]) as image:
            if image.width * image.height > 20_000_000:
                raise ValueError("Image exceeds 20 megapixels.")
            yield 1, _ocr(ImageOps.exif_transpose(image), executable, language)


def _split(text: str, separators: tuple[str, ...]) -> Iterator[str]:
    if len(text) <= CHUNK_SIZE - OVERLAP:
        yield text
    elif not separators:
        size = CHUNK_SIZE - OVERLAP
        for start in range(0, len(text), size):
            yield text[start:start + size]
    else:
        separator, *remaining = separators
        pieces = text.split(separator)
        packed = ""
        for index, part in enumerate(pieces):
            piece = part + (separator if index < len(pieces) - 1 else "")
            if len(packed) + len(piece) > CHUNK_SIZE - OVERLAP:
                if packed:
                    yield packed
                    packed = ""
                yield from _split(piece, tuple(remaining))
            else:
                packed += piece
        if packed:
            yield packed


def chunks(text: str) -> Iterator[str]:
    tail = ""
    for part in _split(text, ("\n\n", "\n", ". ", " ")):
        chunk = (tail + part).strip()
        if chunk:
            yield chunk
        tail = (tail + part)[-OVERLAP:]
