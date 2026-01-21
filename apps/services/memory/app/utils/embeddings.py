import hashlib
import random

EMBEDDING_DIM = 1536

def generate_stub_embedding(text: str)-> list[float]:
    """ 
    Deterministic fake embedding.
    Same text -> same Vector.
    """
    seed = int(hashlib.sha256(text.encode()).hexdigest(), 16) % (2**32)
    rnd = random.Random(seed)
    
    return [rnd.random() for _ in range(EMBEDDING_DIM)]