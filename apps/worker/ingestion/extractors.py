import os
import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

MAX_RESPONSE_MB = int(os.getenv("MAX_FETCH_MB", "10"))


def normalize_text(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\x00", " ")
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = "\n".join(line.rstrip() for line in s.split("\n"))
    s = re.sub(r"[ \t]{2,}", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def extract_text_from_pdf(file_path: str) -> str:
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"PDF not found: {file_path}")

    reader = PdfReader(file_path)
    parts = []
    empty_pages = 0

    for page in reader.pages:
        t = (page.extract_text() or "").strip()
        if t:
            parts.append(t)
        else:
            empty_pages += 1

    text = "\n\n".join(parts)
    text = normalize_text(text)

    if reader.pages and empty_pages / len(reader.pages) > 0.6:
        text += "\n\n[NOTE] Many pages had no extractable text, PDF may be scanned and require OCR."

    return text


def extract_text_from_url(url: str, timeout: int = 20) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid URL scheme: {parsed.scheme}")
    if not parsed.netloc:
        raise ValueError(f"Invalid URL: {url}")

    headers = {"User-Agent": "memoire-worker/1.0"}
    resp = requests.get(url, headers=headers, timeout=timeout, stream=True)
    resp.raise_for_status()

    content_length = resp.headers.get("Content-Length")
    if content_length and int(content_length) > MAX_RESPONSE_MB * 1024 * 1024:
        raise ValueError(f"Response too large: {content_length} bytes")

    chunks = []
    total = 0
    limit = MAX_RESPONSE_MB * 1024 * 1024
    for chunk in resp.iter_content(chunk_size=65536, decode_unicode=True):
        total += len(chunk)
        if total > limit:
            raise ValueError(f"Response exceeded {MAX_RESPONSE_MB}MB limit")
        chunks.append(chunk)

    html = "".join(chunks)
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "header", "footer", "nav", "aside"]):
        tag.decompose()

    main = soup.select_one("article") or soup.select_one("main")

    if main:
        raw = main.get_text(separator="\n")
    else:
        raw = soup.get_text(separator="\n")

    return normalize_text(raw)
