from typing import List
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# config
EMBEDDING_DIM = 1536
MODEL = "text-embedding-3-small"

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def embed_text(text:str) -> List[float]:
    """ 
    convert text to embeddings using OpenAI API
    """
    
    text = (text or "").strip()
    if not text:
        raise ValueError("Text is required")
    
    response = client.embeddings.create(
        model = MODEL,
        input = text,
    )
    vector = response.data[0].embedding
    
    if len(vector) != EMBEDDING_DIM:
        raise ValueError(f"Expected {EMBEDDING_DIM} dimensions, got {len(vector)}")
    
    return vector