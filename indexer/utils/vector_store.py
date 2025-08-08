import time
from typing import Optional, Dict
from qdrant_client import QdrantClient, models
from qdrant_client.models import VectorParams, Distance, PointStruct
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config as config

class VectorStore:
    """
    VectorStore is a high-level interface for managing a Qdrant vector database collection
    that supports both text and image embeddings. It simplifies collection setup, document
    insertion (with text and/or image embeddings and optional metadata), and similarity search.
    This class abstracts Qdrant operations, enabling seamless upsert and retrieval of multimodal data.
    """

    def __init__(
        self,
        collection_name: str,
        vector_sizes: Dict[str, int] = {"text_embedding": 384, "image_embedding": 512},
        distance: Distance = Distance.COSINE
    ):
        self.collection_name = collection_name
        self.client = QdrantClient(url=config.QDRANT_URL, api_key=config.QDRANT_API_KEY)
        self.vector_sizes = vector_sizes
        self.distance = distance
        self.text_embedding_model = config.TEXT_EMBEDDING_MODEL
        self.image_embedding_model = config.IMAGE_EMBEDDING_MODEL

        self._initialize_collection()

    def _initialize_collection(self):
        existing = [c.name for c in self.client.get_collections().collections]
        if self.collection_name in existing:
            return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config={
                "text_embedding": VectorParams(size=self.vector_sizes["text_embedding"], distance=self.distance),
                "image_embedding": VectorParams(size=self.vector_sizes["image_embedding"], distance=self.distance),
            }
        )

    def insert_document(
        self,
        text: Optional[str] = None,
        image: Optional[str] = None,
        metadata: Optional[dict] = None,
        id: Optional[int] = None
    ):
        if not text and not image:
            raise ValueError("At least one of `text` or `image` must be provided.")

        vectors = {}
        if text:
            vectors["text_embedding"] = models.Document(text=text, model=self.text_embedding_model)
        if image:
            vectors["image_embedding"] = models.Image(image=image, model=self.image_embedding_model)

        point = PointStruct(
            id=id or self._generate_id(),
            vector=vectors,
            payload=metadata or {}
        )

        self.client.upsert(
            collection_name=self.collection_name,
            points=[point]
        )

    def _generate_id(self):
        return int(time.time() * 1000)
    
    def query(
        self,
        query_text: str,
        top_k: int = 3,
        using: str = "text_embedding",
    ):
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=models.Document(text=query_text, model=self.text_embedding_model),
            limit=top_k,
            using=using
        )
        return results


if __name__ == "__main__":
    store = VectorStore("products-data")

    store.insert_document(text="This is a product", image=None)

    results = store.query("What is a review?", 3)
    print(results)
