"""
Embedding Service using OpenAI API.
Lightweight alternative to sentence-transformers (no PyTorch needed).
"""
import os
from typing import List
import json
from openai import OpenAI

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Using OpenAI's efficient embedding model
MODEL_NAME = "text-embedding-3-small"  # 1536 dimensions, fast, cheap


def get_embedding(text: str) -> List[float]:
    """Generate embedding for a single text using OpenAI API."""
    try:
        response = client.embeddings.create(
            model=MODEL_NAME,
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"OpenAI embedding error: {e}")
        # Return zero vector as fallback
        return [0.0] * 1536


def get_embeddings(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for multiple texts (batched)."""
    try:
        response = client.embeddings.create(
            model=MODEL_NAME,
            input=texts
        )
        return [item.embedding for item in response.data]
    except Exception as e:
        print(f"OpenAI batch embedding error: {e}")
        return [[0.0] * 1536 for _ in texts]


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    import math
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot_product / (norm1 * norm2)


def embedding_to_json(embedding: List[float]) -> str:
    """Serialize embedding for database storage."""
    return json.dumps(embedding)


def json_to_embedding(json_str: str) -> List[float]:
    """Deserialize embedding from database."""
    return json.loads(json_str)
