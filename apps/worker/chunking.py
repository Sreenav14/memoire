from __future__ import annotations
from typing import List, Optional, Tuple
from dataclasses import dataclass
import re


from .extractors import normalize_text


_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


@dataclass
class Chunk:
    chunk_index: int
    text: str
    char_start: int
    char_end: int
    section_title: Optional[str] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    
def _iter_paragraph_spans(text: str) -> List[Tuple[int, int]]:
    """ 
    Return (start, end) indices for each paragraph in the text.
    """
    
    spans:List[Tuple[int, int]] = []
    n = len(text)
    i = 0
    
    while i<n:
        while i<n and text[i] in ("\n", " " , "\t"):
            i += 1
        if i >=n :
            break
        
        start = i
        # paragraph ends at double newline
        while i<n:
            if i+1 < n and text[i] == "\n" and text[i+1] == "\n":
                end = i
                break
            i += 1
        else:
            end = i
            
        if end > start:
            spans.append((start, end))
            
        # skip blank line separator
        while i<n and text[i] == "\n":
            i += 1
    
    return spans

def _split_sentences_with_spans(par_text: str, par_start: int) -> List[Tuple[int, int]]:
    """ 
    Split paragraph into sentence spans
    """
    spans: List[Tuple[int, int]] = []
    local_start = 0
    
    for m in _SENT_SPLIT.finditer(par_text):
        local_end = m.start()
        if local_end > local_start:
            spans.append((par_start + local_start, par_start + local_end))
        local_start = m.end()
        
    if local_start < len(par_text):
        spans.append((par_start + local_start, par_start + len(par_text)))
        
    return spans

def chunk_text_smart_with_offsets(
    text: str,
    chunk_size: int=800,
    overlap: int = 120, 
    )-> List[Chunk]:
    """
    Chunking strategy (MVP but solid):
    - Normalize text (your normalize_text keeps paragraph structure)
    - Prefer paragraph boundaries (split by blank lines)
    - If a paragraph is too large, split by sentences
    - Apply overlap by expanding the next chunk's start backwards by `overlap`
      (keeps offsets valid and avoids physically copying tail text)
    """
    text = normalize_text(text)
    if not text:
        return []
    
    paragraph_spans = _iter_paragraph_spans(text)
    
    raw_chunks: List[Tuple[int, int]] = []
    cur_s: Optional[int] = None
    cur_e: Optional[int] = None
    
    def cur_len()-> int:
        if cur_s is None or cur_e is None:
            return 0
        return cur_e - cur_s
    
    def flush():
        nonlocal cur_s, cur_e
        if cur_s is not None and cur_e is not None and cur_e > cur_s:
            raw_chunks.append((cur_s, cur_e))
        cur_s, cur_e = None, None
                
    for ps, pe in paragraph_spans:
        p_len = pe - ps
        
        # start a new chunk if none exists yet
        if cur_s is None:
            if p_len <= chunk_size:
                cur_s, cur_e = ps, pe
            else:
                # paragraph is huge, split by sentences
                sent_spans = _split_sentences_with_spans(text[ps:pe], ps)
                buf_s: Optional[int] = None
                buf_e: Optional[int] = None
                
                for ss,se in sent_spans:
                    if buf_s is None:
                        buf_s, buf_e = ss, se
                        continue
                    
                    if (se - buf_s) <= chunk_size:
                        buf_e = se
                    else:
                        raw_chunks.append((buf_s, buf_e))
                        buf_s, buf_e = ss, se
                if buf_s is not None and buf_e is not None:
                    raw_chunks.append((buf_s, buf_e))
            continue
        
        # append this paragraph into the current chunk
        if cur_len() + p_len + 2 <= chunk_size:
            cur_e = pe
        else:
            flush()
            #  now paragraphs starts a new chunking
            if p_len <= chunk_size:
                cur_s, cur_e = ps, pe
            else:
                sent_spans = _split_sentences_with_spans(text[ps:pe], ps)
                buf_s = None
                buf_e = None
                for ss, se in sent_spans:
                    if buf_s is None:
                        buf_s, buf_e = ss, se
                        continue
                    
                    if (se - buf_s) <= chunk_size:
                        buf_e = se
                    else:
                        raw_chunks.append((buf_s, buf_e))
                        buf_s, buf_e = ss, se
                        
                if buf_s is not None and buf_e is not None:
                    raw_chunks.append((buf_s, buf_e))
    
    flush()
    
    # Apply overlap 
    overlapped: List[Tuple[int, int]] = []
    for i, (s,e) in enumerate(raw_chunks):
        if i==0 or overlap <=0:
            overlapped.append((s,e))
        else:
            new_s = max(0, s - overlap)
            overlapped.append((new_s, e))
            
    # build output chunks
    out: List[Chunk] = []
    for idx, (s,e) in enumerate(overlapped):
        slice = text[s:e]
        left_trim = len(slice) - len(slice.lstrip())
        right_trim = len(slice) - len(slice.rstrip())
        
        new_s = s + left_trim
        new_e = e - right_trim
        
        c_text = text[new_s:new_e]
        if not c_text.strip():
            continue
        out.append(
            Chunk(
                chunk_index = idx,
                text = c_text,
                char_start = s,
                char_end = e,
            )
        )
    return out
        
    
if __name__ == "__main__":
    sample = "Hello world.\n\nThis is a paragraph. It has two sentences. Great.\n\nAnother paragraph."
    chunks = chunk_text_smart_with_offsets(sample, chunk_size=40, overlap=10)
    for c in chunks:
        print(c.chunk_index, c.char_start, c.char_end, repr(c.text))
