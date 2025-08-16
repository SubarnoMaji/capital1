import logging
import sys
import os
from typing import Optional, List

# Ensure config import works regardless of working directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../")))
from agents.config import Config

from gradio_client import Client as GradioClient
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from retriever.metadata_selector import LLMMetadataSubsetSelector
from langchain.tools import tool

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def get_embedding_from_hf(text: str) -> list:
    """
    Get embedding for the input text using the HuggingFace Gradio API.
    """
    logger.info(f"Getting embedding for text via GradioClient: {text!r}")
    client = GradioClient(getattr(Config, "HF_GRADIO_EMBEDDING_SPACE"))
    result = client.predict(
        texts=[text],
        api_name="/predict"
    )

    if not isinstance(result, dict) or "vectors" not in result:
        raise ValueError(f"Unexpected embedding format: {result}")

    vectors = result["vectors"]
    if not vectors or not isinstance(vectors[0], list):
        raise ValueError(f"Unexpected vectors format: {vectors}")

    embedding = vectors[0]
    if not all(isinstance(x, (float, int)) for x in embedding):
        raise ValueError("Invalid embedding format — expected list of floats.")

    return embedding

def build_qdrant_filter_from_metadata(metadata_subset):
    if not metadata_subset:
        return None

    INDEXED_FIELDS = getattr(Config, "QDRANT_INDEXED_FIELDS", ["year"])
    conditions = []

    for entry in metadata_subset:
        for key, value in entry.items():
            if key not in INDEXED_FIELDS:
                logger.debug(f"Skipping metadata key '{key}' — not indexed.")
                continue
            if isinstance(value, (str, int, float, bool)):
                conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))
            elif isinstance(value, list) and len(value) == 1 and isinstance(value[0], (str, int, float, bool)):
                conditions.append(FieldCondition(key=key, match=MatchValue(value=value[0])))
            else:
                logger.debug(f"Skipping key '{key}' — unsupported type for filtering.")

    logger.info(f"Built OR filter with {len(conditions)} conditions")
    return Filter(should=conditions) if conditions else None

@tool("search_qdrant_with_metadata", return_direct=False)
def search_with_metadata_tool(user_query: str, max_metadata: int = 5, limit: int = 5, use_metadata_filter: bool = True) -> List[dict]:
    """
    Search documents in Qdrant using a vector embedding, optionally applying an LLM-selected metadata filter.

    Args:
        user_query (str): The search query.
        max_metadata (int): Maximum number of metadata fields to request from the selector.
        limit (int): Number of results to return.
        use_metadata_filter (bool): Whether to use metadata filtering (True) or not (False).

    Returns:
        List[dict]: Search results with 'id', 'score', 'text', and 'metadata'.
    """
    logger.info(f"Starting search for query: {user_query!r}")

    # Init Qdrant client
    client = QdrantClient(url=Config.QDRANT_URL, api_key=Config.QDRANT_API_KEY)

    # Decide whether to use metadata filtering
    qdrant_filter = None
    if use_metadata_filter:
        selector = LLMMetadataSubsetSelector()
        relevant_subset = selector.select_relevant_metadata(user_query, max_metadata=max_metadata)
        logger.info(f"Relevant metadata subset: {relevant_subset}")
        qdrant_filter = build_qdrant_filter_from_metadata(relevant_subset)
    else:
        logger.info("Skipping metadata filtering — retrieving purely by vector similarity.")

    # Get embedding
    query_vector = get_embedding_from_hf(user_query)
   
    # Perform search
    try:
        results = client.query_points(
            collection_name=Config.COLLECTION_NAME,
            query=query_vector,
            query_filter=qdrant_filter,
            limit=limit,
            using="text_embedding"
        ).points
    except Exception as e:
        logger.error(f"Qdrant query failed: {e}")
        raise

    # Format results as list of dicts
    output = []
    for r in results:
        result_dict = {
            "id": r.id,
            "score": r.score,
            "text": r.payload.get("text"),
            "metadata": r.payload
        }
        logger.info(result_dict)
        output.append(result_dict)

    return output

if __name__ == "__main__":
    # Example standalone usage
    res = search_with_metadata_tool.run("how to become agri scientist", use_metadata_filter=True)
    print(res)
