"""
Embedding Service using sentence-transformers.
Runs locally without API key.
"""
from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List, Union
import json

# Load model once at import (this will download on first run)
# Using a lightweight model for speed
MODEL_NAME = "all-MiniLM-L6-v2"  # 384 dimensions, fast
_model = None


def get_model():
    """Lazy load the embedding model."""
    global _model
    if _model is None:
        print(f"Loading embedding model: {MODEL_NAME}...")
        _model = SentenceTransformer(MODEL_NAME)
        print("Model loaded!")
    return _model


def get_embedding(text: str) -> List[float]:
    """Generate embedding for a single text."""
    model = get_model()
    embedding = model.encode(text, convert_to_numpy=True)
    return embedding.tolist()


def get_embeddings(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for multiple texts (batched)."""
    model = get_model()
    embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=True)
    return embeddings.tolist()


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    a = np.array(vec1)
    b = np.array(vec2)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def embedding_to_json(embedding: List[float]) -> str:
    """Serialize embedding for database storage."""
    return json.dumps(embedding)


def json_to_embedding(json_str: str) -> List[float]:
    """Deserialize embedding from database."""
    return json.loads(json_str)
