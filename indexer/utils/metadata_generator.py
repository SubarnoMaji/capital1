import os
import sys
import logging
import json
from pathlib import Path
from collections import defaultdict
from rapidfuzz import fuzz
import concurrent.futures

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

from dotenv import load_dotenv

# Use Google Gemini API directly
import google.generativeai as genai

METADATA_SAVE_DIR = getattr(Config, "METADATA_SAVE_DIR", ".cache/metadata_list")
Path(METADATA_SAVE_DIR).mkdir(parents=True, exist_ok=True)
METADATA_LOG_FILE = os.path.join(METADATA_SAVE_DIR, "all_metadata.json")

load_dotenv()

sample_json = {
    "document_type": "farming report",
    "key_entities": ["maize", "fertilizer", "irrigation"],
    "topics": ["crop yield", "pest management", "soil health"],
    "year": 2024,
}

prompt_template = """
You are an expert assistant for an agriculture and farming knowledge system.

Analyze the provided document and extract structured metadata relevant to agriculture and farming. Focus on type safety and specificity.

<document_name>
{doc_name}
</document_name>

<document>
{doc_text}
</document>

Return the results as a JSON object with the following fields, using lowercase for all string values:

- "document_type" (string): The specific type of document (e.g., "farming report", "crop advisory", "weather bulletin", "market update", "government policy").
- "key_entities" (list of strings): The most important crops, chemicals, equipment, organizations, or people mentioned.
- "topics" (list of strings): Main agricultural topics, practices, or issues discussed (e.g., "irrigation", "pest management", "crop yield", "organic farming").
- "year" (integer): The year the document was created or is about.

All text values in the JSON output must be in lowercase.

Example output:
{sample_json}

Return only the JSON object in the specified format.
"""


class MetadataGrouper:
    def __init__(self, fuzzy_threshold=90, max_workers=None):
        """
        :param fuzzy_threshold: Similarity threshold (0-100) for grouping.
        :param max_workers: Number of threads for parallel fuzzy scoring.
        """
        self.fuzzy_threshold = fuzzy_threshold
        self.max_workers = max_workers

    def _cheap_bucket_key(self, metadata):
        """
        Bucket metadata to reduce comparisons.
        Uses first 2 chars of first key_entity + year + topic count.
        """
        key_entities = metadata.get("key_entities", [])
        first_entity = key_entities[0] if key_entities else ""
        year = metadata.get("year", "")
        return f"{first_entity[:2].lower()}_{len(metadata.get('topics', []))}_{year}"

    def _fuzzy_score(self, meta_a, meta_b):
        """
        Compute fuzzy similarity using original spacing.
        """
        str_a = (meta_a.get("document_type", "") + " " +
                 " ".join(meta_a.get("key_entities", []) + meta_a.get("topics", [])))
        str_b = (meta_b.get("document_type", "") + " " +
                 " ".join(meta_b.get("key_entities", []) + meta_b.get("topics", [])))

        return fuzz.token_sort_ratio(str_a, str_b)

    def group(self, metadata_list):
        """
        Group similar metadata objects based on fuzzy matching within buckets.
        """
        # Step 1: Bucket metadata to limit comparisons
        buckets = defaultdict(list)
        for md in metadata_list:
            buckets[self._cheap_bucket_key(md)].append(md)

        groups = []

        # Step 2: Compare only inside each bucket
        for _, bucket in buckets.items():
            visited = set()
            for i, meta in enumerate(bucket):
                if i in visited:
                    continue
                group = [meta]
                visited.add(i)

                with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    futures = {
                        executor.submit(self._fuzzy_score, meta, bucket[j]): j
                        for j in range(i + 1, len(bucket)) if j not in visited
                    }
                    for future in concurrent.futures.as_completed(futures):
                        j = futures[future]
                        if future.result() >= self.fuzzy_threshold:
                            group.append(bucket[j])
                            visited.add(j)

                groups.append(group)

        return groups


class MetadataGenerator:
    """
    A class to generate document metadata using Google Gemini API directly.
    Only generates metadata for the complete document, not for each chunk.
    Instead of caching, appends all unique generated metadata to a JSON file.
    Optionally groups metadata using MetadataGrouper if use_grouping is True.
    """
    def __init__(self, use_grouping=False, grouper_kwargs=None, model_name=None, google_api_key=None):
        # Use Google API key from env or config
        self.google_api_key = google_api_key or os.getenv("GOOGLE_API_KEY") or getattr(Config, "GOOGLE_API_KEY", None)
        if not self.google_api_key:
            raise ValueError("GOOGLE_API_KEY environment variable or config not set.")

        self.model_name = model_name or "gemini-2.5-flash-lite"

        genai.configure(api_key=self.google_api_key)
        self.model = genai.GenerativeModel(self.model_name)

        logging.basicConfig(
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            level=logging.INFO,
        )
        self.logger = logging.getLogger(__name__)

        # Track unique metadata in memory for this run
        self.seen_metadata = set()

        self.use_grouping = use_grouping
        self.grouper = None
        if self.use_grouping:
            if grouper_kwargs is None:
                grouper_kwargs = {}
            self.grouper = MetadataGrouper(**grouper_kwargs)

    def _format_prompt(self, doc_text, doc_name):
        return prompt_template.format(
            doc_text=doc_text,
            doc_name=doc_name,
            sample_json=json.dumps(sample_json, indent=4),
        )

    def generate(self, doc_text, doc_name):
        content = self._format_prompt(doc_text, doc_name)

        try:
            # Use Gemini API directly
            response = self.model.generate_content(content)
            enhanced_data = response.text.strip() if hasattr(response, "text") else response.candidates[0].content.parts[0].text.strip()

            enhanced_data = enhanced_data.replace("```json", "").replace("```", "").strip()

            try:
                addn_metadata = json.loads(enhanced_data)
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to parse JSON from model output: {enhanced_data}")
                raise e

            # Use a stringified version for uniqueness check
            metadata_str = json.dumps(addn_metadata, sort_keys=True)
            if metadata_str not in self.seen_metadata:
                self.seen_metadata.add(metadata_str)
                # Save as JSON array, appending new objects
                if os.path.exists(METADATA_LOG_FILE):
                    try:
                        with open(METADATA_LOG_FILE, "r", encoding="utf-8") as f:
                            existing = json.load(f)
                        if not isinstance(existing, list):
                            existing = []
                    except Exception:
                        existing = []
                else:
                    existing = []
                existing.append(addn_metadata)
                with open(METADATA_LOG_FILE, "w", encoding="utf-8") as f:
                    json.dump(existing, f, ensure_ascii=False, indent=4)
                self.logger.info(f"Appended new unique metadata for {doc_name} to {METADATA_LOG_FILE}")
            else:
                self.logger.info(f"Metadata for {doc_name} already exists in this run, not appending.")

            # If grouping is enabled, group all metadata in the log file and return the group containing this metadata
            if self.use_grouping:
                try:
                    with open(METADATA_LOG_FILE, "r", encoding="utf-8") as f:
                        all_metadata = json.load(f)
                    groups = self.grouper.group(all_metadata)
                    # Find the group containing the current metadata
                    for group in groups:
                        if addn_metadata in group:
                            return group
                    # If not found, just return the metadata
                    return [addn_metadata]
                except Exception as e:
                    self.logger.error(f"Error during grouping: {str(e)}")
                    return [addn_metadata]
            else:
                return addn_metadata

        except Exception as e:
            self.logger.error(f"Error generating metadata: {str(e)}")
            return {
                "document_type": None,
                "key_entities": [],
                "topics": [],
                "year": None,
            }

if __name__ == "__main__":
    import PyPDF2

    pdf_path = r"C:\Users\subar\OneDrive\Desktop\capitalone\indexer\utils\documents\Draft_RRs_JSO_inNCONF.pdf"
    doc_name = "Subarno_Resume (2).pdf"

    # Extract text from the PDF
    with open(pdf_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        doc_text = ""
        for page in reader.pages:
            doc_text += page.extract_text() or ""

    metadata_generator = MetadataGenerator(use_grouping=True)
    metadata = metadata_generator.generate(doc_text, doc_name)
    print(json.dumps(metadata, indent=4, ensure_ascii=False))
