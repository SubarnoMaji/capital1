import os
import sys
from typing import Optional, Dict, Any
from pydantic import Field

import time
from qdrant_client import QdrantClient, models
from qdrant_client.models import Distance, Filter, FieldCondition, MatchValue
import logging

from retriever.metadata_generator import LLMMetadataSubsetSelector

from langchain.tools import BaseTool

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../")))
from agents.config import Config

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("retrieval_tool")

def _build_qdrant_filter_from_metadata(metadata: Dict[str, Any]) -> Optional[Filter]:
    """
    Build a Qdrant Filter object from a metadata dictionary.
    Only include fields that are indexed in Qdrant for filtering.
    Handles only primitive types (str, int, float, bool) for filtering.
    Ignores keys with list or dict values, as Qdrant's MatchValue expects a single value.
    """
    if not metadata:
        return None
    # List of fields that are indexed in Qdrant and safe to filter on.
    # You must ensure these fields are indexed in your Qdrant collection.
    INDEXED_FIELDS = getattr(Config, "QDRANT_INDEXED_FIELDS", ["year"])  # Example: ["year", "topics"]
    conditions = []
    for key, value in metadata.items():
        if key not in INDEXED_FIELDS:
            logger.warning(f"Skipping metadata key '{key}' for filtering: not indexed in Qdrant. See https://medium.com/@vandriichuk/comprehensive-guide-to-filtering-in-qdrant-9fa5e9ad8e7b")
            continue
        # Only allow primitive types for filtering
        if isinstance(value, (str, int, float, bool)):
            conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))
        # If value is a list with a single primitive element, use that element
        elif isinstance(value, list) and len(value) == 1 and isinstance(value[0], (str, int, float, bool)):
            conditions.append(FieldCondition(key=key, match=MatchValue(value=value[0])))
        else:
            logger.warning(f"Skipping metadata key '{key}' for filtering: value is not a primitive or single-element list.")
    return Filter(must=conditions) if conditions else None

class Retriever:
    def __init__(self, collection_name, text_embedding_model, qdrant_url, qdrant_api_key):
        self.collection_name = collection_name
        self.text_embedding_model = text_embedding_model
        self.client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)

    def query(
        self, 
        query_text, 
        top_k=3, 
        using="text_embedding", 
        use_metadata_filter: bool = False, 
        metadata: Optional[Dict[str, Any]] = None
    ):
        logger.info(
            f"Querying collection '{self.collection_name}' for top {top_k} results using '{using}' embedding."
            f"{' With metadata filtering.' if use_metadata_filter else ''}"
        )
        try:
            filter_obj = None
            if use_metadata_filter and metadata:
                filter_obj = _build_qdrant_filter_from_metadata(metadata)
                if filter_obj is None or not filter_obj.must:
                    logger.warning("No valid metadata fields for filtering; proceeding without filter.")
                    filter_obj = None

            results = self.client.query_points(
                collection_name=self.collection_name,
                query=models.Document(text=query_text, model=self.text_embedding_model),
                limit=top_k,
                using=using,
                query_filter=filter_obj
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

def retrieve_documents(
    query, 
    top_k=3, 
    use_metadata_filter: bool = False, 
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Retrieve top_k documents from the vector store for the given query.
    Optionally filter by metadata if use_metadata_filter is True and metadata is provided.
    Only indexed metadata fields will be used for filtering.
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
    results = retriever.query(
        query_text=query, 
        top_k=top_k, 
        use_metadata_filter=use_metadata_filter, 
        metadata=metadata
    )
    return results

class RetrievalTool(BaseTool):
    name: str = "retrieval_tool"
    description: str = (
        "Retrieve top-k relevant documents from the vector store given a query string. "
        "Optionally filter by metadata if use_metadata_filter is True and metadata is provided. "
    )
    top_k: int = Field(default=3, description="Number of documents to retrieve")
    use_metadata_filter: bool = Field(default=False, description="Whether to use metadata filtering")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Metadata to filter on if use_metadata_filter is True")

    def __init__(self, top_k: int = 3, use_metadata_filter: bool = False, metadata: Optional[Dict[str, Any]] = None, **kwargs):
        super().__init__(top_k=top_k, use_metadata_filter=use_metadata_filter, metadata=metadata, **kwargs)

    def _run(
        self, 
        query: str, 
        top_k: Optional[int] = None, 
        use_metadata_filter: Optional[bool] = None, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> list:
        k = top_k if top_k is not None else self.top_k
        use_filter = use_metadata_filter if use_metadata_filter is not None else self.use_metadata_filter
        meta = metadata if metadata is not None else self.metadata
        return retrieve_documents(query, k, use_filter, meta)

    async def _arun(
        self, 
        query: str, 
        top_k: Optional[int] = None, 
        use_metadata_filter: Optional[bool] = None, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> list:
        return self._run(query, top_k, use_metadata_filter, metadata)

if __name__ == "__main__":

    user_query = "how to become agri scientist"

    selector = LLMMetadataSubsetSelector()
    relevant_subset = selector.select_relevant_metadata(user_query, max_metadata=5)
    # Use the first relevant metadata entry if available, but only pass primitive fields for filtering
    metadata_to_use = None
    if relevant_subset:
        # Only keep primitive fields for filtering, and only those that are indexed in Qdrant
        INDEXED_FIELDS = getattr(Config, "QDRANT_INDEXED_FIELDS", ["year"]) 
        candidate = relevant_subset[0]
        metadata_to_use = {
            k: v for k, v in candidate.items()
            if k in INDEXED_FIELDS and (
                isinstance(v, (str, int, float, bool)) or
                (isinstance(v, list) and len(v) == 1 and isinstance(v[0], (str, int, float, bool)))
            )
        }
        if not metadata_to_use:
            logger.warning("No valid indexed metadata fields found for filtering. Proceeding without metadata filter.")
    tool_with_metadata = RetrievalTool(top_k=3, use_metadata_filter=True, metadata=metadata_to_use)
    results_with_metadata = tool_with_metadata.run(user_query)
    print("Query results using metadata from metadata-generator.py:", results_with_metadata)