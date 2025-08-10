import os
import sys
import logging

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "utils"))

from utils.file_parser import PDFParser
from utils.vector_store import VectorStore
from utils.metadata_generator import MetadataGenerator
from config import Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("indexer")

def index_documents(documents_dir, collection_name=Config.COLLECTION_NAME):
    store = VectorStore(collection_name)
    metadata_gen = MetadataGenerator()
    for filename in os.listdir(documents_dir):
        if filename.lower().endswith(".pdf"):
            pdf_path = os.path.join(documents_dir, filename)
            logger.info(f"Processing file: {filename}")
            try:
                parser = PDFParser(pdf_path)
                extracted_text = parser.extract_text()
                logger.debug(f"Extracted text from {filename}: {extracted_text[:100]}..." if extracted_text else "No text extracted.")

                generated_metadata = metadata_gen.generate(extracted_text, filename)
                logger.info(f"Generated metadata for {filename}: {generated_metadata}")

                payload = {"source": filename}
                if isinstance(generated_metadata, dict):
                    payload.update(generated_metadata)
                else:
                    payload["generated_metadata"] = generated_metadata

                store.insert_document(
                    text=extracted_text,
                    metadata=payload,
                    chunk=True,
                    chunk_size=1000,
                    chunk_overlap=200
                )
                logger.info(f"Inserted document from {filename} (with chunking and metadata)")
            except FileNotFoundError as e:
                logger.error(f"File not found: {e}")
                logger.error(f"Please ensure the PDF file '{filename}' exists in the 'documents' folder.")
            except Exception as e:
                logger.error(f"Error processing {filename}: {e}")

if __name__ == "__main__":
    documents_dir = os.path.join(os.path.dirname(__file__), "utils", "documents")
    logger.info(f"Looking for PDF documents in directory: {documents_dir}")
    try:
        index_documents(documents_dir)
        logger.info("Indexing complete.")
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
