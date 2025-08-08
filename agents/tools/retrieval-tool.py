
import os
import sys
from typing import Optional
from pydantic import Field

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import Config

import time
from qdrant_client import QdrantClient, models
from qdrant_client.models import Distance
import logging

from langchain.tools import BaseTool

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("retrieval_tool")

class Retriever:
    def __init__(self, collection_name, text_embedding_model, qdrant_url, qdrant_api_key):
        self.collection_name = collection_name
        self.text_embedding_model = text_embedding_model
        self.client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)

    def query(self, query_text, top_k=3, using="text_embedding"):
        logger.info(f"Querying collection '{self.collection_name}' for top {top_k} results using '{using}' embedding.")
        try:
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=models.Document(text=query_text, model=self.text_embedding_model),
                limit=top_k,
                using=using
            )
            logger.info(f"Query successful. Retrieved {len(results.points)} results.")
        except Exception as e:
            logger.error(f"Query failed: {e}")
            raise

        return [
            {
                "id": r.id,
                "score": r.score,
                "text": r.payload.get("text"),
                "metadata": r.payload
            }
            for r in results.points
        ]

def retrieve_documents(query, top_k=3):
    """
    Retrieve top_k documents from the vector store for the given query.
    """
    collection_name = Config.COLLECTION_NAME
    text_embedding_model = Config.TEXT_EMBEDDING_MODEL
    qdrant_url = Config.QDRANT_URL
    qdrant_api_key = Config.QDRANT_API_KEY
    
    # Validate required parameters
    if not text_embedding_model:
        raise ValueError("TEXT_EMBEDDING_MODEL is not set in configuration")
    if not qdrant_url:
        raise ValueError("QDRANT_URL is not set in configuration")
    if not qdrant_api_key:
        raise ValueError("QDRANT_API_KEY is not set in configuration")

    retriever = Retriever(
        collection_name=collection_name,
        text_embedding_model=text_embedding_model,
        qdrant_url=qdrant_url,
        qdrant_api_key=qdrant_api_key
    )
    results = retriever.query(query, top_k)
    return results

class RetrievalTool(BaseTool):
    name: str = "retrieval_tool"
    description: str = "Retrieve top-k relevant documents from the vector store given a query string."
    top_k: int = Field(default=3, description="Number of documents to retrieve")

    def __init__(self, top_k: int = 3, **kwargs):
        super().__init__(top_k=top_k, **kwargs)

    def _run(self, query: str, top_k: Optional[int] = None) -> list:
        k = top_k if top_k is not None else self.top_k
        return retrieve_documents(query, k)

    async def _arun(self, query: str, top_k: Optional[int] = None) -> list:
        return self._run(query, top_k)

if __name__ == "__main__":

    query = "what did he do in Morgan Stanley?"
    tool = RetrievalTool(top_k=3)
    results = tool.run(query)
    print("Query results:", results)