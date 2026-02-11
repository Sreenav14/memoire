import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
import re

def normalize_text(s: str) -> str:
    if not s:
        return ""
    s=s.replace("\x00", " ")
    s = s.replace("\r\n", "\n").replace("\r","\n")
    s = "\n".join(line.rstrip() for line in s.split("\n"))
    s=re.sub(fr"[ \t]{2,}", " ",s)
    s=re.sub(fr"\n{3,}","\n\n", s)
    return s.strip()

def extract_text_from_pdf(file_path: str) -> str:
    reader = PdfReader(file_path)
    parts = []
    empty_pages = 0
    
    for idx, page in enumerate(reader.pages):
        t = (page.extract_text() or "").strip()
        if t:
            parts.append(t)
        else:
            empty_pages +=1
    
    text = "\n\n".join(parts)
    text = normalize_text(text)
    
    if reader.pages and empty_pages / len(reader.pages) > 0.6:
        text += "\n\n[NOTE] Many pages had no extractable text, PDF may be scanned and require OCR."
        
    return text

def extract_text_from_url(url: str, timeout: int = 20) -> str:
    headers = {"User-Agent": "memoire-worker/1.0"}
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    
    soup = BeautifulSoup(resp.text, "html.parser")
    
    for tag in soup(["script", "style", "header","footer", "nav", "aside"]):
        tag.decompose()
    
    main = soup.select_one("article") or soup.select_one("main")
    
    if main:
        raw = main.get_text(separator="\n")
    else:
        raw = soup.get_text(separator="\n")
    
    return normalize_text(raw)
    
    