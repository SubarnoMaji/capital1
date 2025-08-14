import os
import sys
import json
import logging
from typing import List, Optional, Dict, Any

from langchain_openai import ChatOpenAI

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../")))
from agents.config import Config

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def load_metadata_file() -> List[Dict[str, Any]]:
    """
    Loads the metadata file specified in Config and returns its content as a list of dicts.
    """
    metadata_path = getattr(Config, "METADATA_FILE", None)
    if not metadata_path or not os.path.exists(metadata_path):
        logger.error(f"Metadata file not found at {metadata_path}")
        return []
    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            logger.error("Metadata file does not contain a list at the top level.")
            return []
        return data
    except Exception as e:
        logger.error(f"Error loading metadata file: {str(e)}")
        return []

class LLMMetadataSubsetSelector:
    """
    Uses an LLM to select the most relevant subset of metadata from the metadata file.
    """

    def __init__(self, openai_api_key: Optional[str] = None, model: str = "gpt-4o"):
        self.openai_api_key = openai_api_key or getattr(Config, "OPENAI_API_KEY", None)
        self.model = model
        self._llm = ChatOpenAI(
            openai_api_key=self.openai_api_key,
            model=self.model,
            temperature=0.0,
            max_tokens=1000,
        )
        self._all_metadata = load_metadata_file()

    def select_relevant_metadata(
        self,
        user_query: str,
        max_metadata: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Uses the LLM to select the most relevant subset of metadata for the user query.

        Args:
            user_query (str): The user's query or information need.
            max_metadata (int): Maximum number of metadata entries to return.

        Returns:
            List[Dict[str, Any]]: The LLM-selected relevant metadata subset.
        """
        all_metadata = self._all_metadata
        # To avoid sending the entire metadata file, filter for candidate entries that are likely relevant.
        # We'll do a simple keyword match on the user query for initial filtering.
        def is_relevant(entry: Dict[str, Any], query: str) -> bool:
            query_lower = query.lower()
            for key in ["document_type", "key_entities", "topics"]:
                value = entry.get(key, "")
                if isinstance(value, list):
                    if any(query_lower in str(item).lower() for item in value):
                        return True
                elif isinstance(value, str):
                    if query_lower in value.lower():
                        return True
            # Also check year if query contains a year
            for word in query.split():
                if word.isdigit() and "year" in entry and str(entry["year"]) == word:
                    return True
            return False

        # First, filter metadata to a smaller candidate set
        candidate_metadata = [entry for entry in all_metadata if is_relevant(entry, user_query)]
        # If nothing matched, fall back to the first N entries
        if not candidate_metadata:
            candidate_metadata = all_metadata[:min(10, len(all_metadata))]
        # Limit the number of candidates sent to the LLM
        candidate_metadata = candidate_metadata[:30]

        prompt = f"""
            You are an expert assistant for an agriculture and farming knowledge system.

            Given the following user query and a list of metadata entries (in JSON), select the most relevant subset of metadata entries for answering the query.

            <user_query>
            {user_query}
            </user_query>

            <all_metadata>
            {json.dumps(candidate_metadata, ensure_ascii=False, indent=2)}
            </all_metadata>

            **Instructions:**
            - Carefully read the user query and the metadata entries.
            - Return only the most relevant metadata entries as a JSON array (list of objects).
            - Do not include any explanation or extra text.
            - Limit the output to at most {max_metadata} entries.
            - If none are relevant, return an empty list [].
            - Preserve the original structure of each metadata entry.

            Example output:
            [
            {{
                "document_type": "...",
                "key_entities": [...],
                "topics": [...],
                "year": ...
            }},
            ...
            ]
            """
        response = self._llm.invoke([{"role": "user", "content": prompt}])
        content = response.content.strip()
        # Remove code block markers if present
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        try:
            subset = json.loads(content)
            if isinstance(subset, dict):
                # Sometimes LLM returns a dict with a key like "results"
                subset = list(subset.values())[0]
            if not isinstance(subset, list):
                logger.error("LLM did not return a list of metadata.")
                return []
            return subset
        except Exception as e:
            logger.error(f"Error parsing LLM metadata subset response: {str(e)}")
            logger.error(f"Raw LLM response: {content}")
            return []

if __name__ == "__main__":
    # Example usage
    user_query = "i want to dance"
    selector = LLMMetadataSubsetSelector()
    relevant_subset = selector.select_relevant_metadata(user_query, max_metadata=5)
    print("Relevant metadata subset:", relevant_subset)