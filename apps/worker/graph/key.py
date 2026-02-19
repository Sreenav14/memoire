import re
import unicodedata

def norm_name(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").strip().lower()
    s = re.sub(r"\s+"," ", s)
    s = re.sub(r"[^\w\s\-\.\+/#]", "", s)
    return s.strip()

def entity_key(entity_type: str, name: str) -> str:
    return f"{entity_type.lower()}:{norm_name(name)}"

def edge_key(src_key: str, relation:str, dst_key: str) -> str:
    rel = norm_name(relation).replace(" ", "_")
    return f"{src_key}|{rel}|{dst_key}"
