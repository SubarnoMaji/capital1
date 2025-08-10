import time
from typing import Optional, Dict
from qdrant_client import QdrantClient, models
from qdrant_client.models import VectorParams, Distance, PointStruct
import os
import sys
import logging

from langchain.text_splitter import RecursiveCharacterTextSplitter

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("vector_store")

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config as config
from utils.file_parser import PDFParser  

class VectorStore:
    """
    VectorStore is a high-level interface for managing a Qdrant vector database collection
    that supports both text and image embeddings. It simplifies collection setup, document
    insertion (with text and/or image embeddings and optional metadata), and similarity search.
    """

    def __init__(
        self,
        collection_name: str,
        vector_sizes: Dict[str, int] = {"text_embedding": 384, "image_embedding": 512},
        distance: Distance = Distance.COSINE
    ):
        logger.info(f"Initializing VectorStore for collection '{collection_name}'")
        self.collection_name = collection_name
        self.client = QdrantClient(url=config.QDRANT_URL, api_key=config.QDRANT_API_KEY)
        self.vector_sizes = vector_sizes
        self.distance = distance
        self.text_embedding_model = config.TEXT_EMBEDDING_MODEL
        self.image_embedding_model = config.IMAGE_EMBEDDING_MODEL

        self._initialize_collection()

    def _initialize_collection(self):
        logger.info(f"Checking if collection '{self.collection_name}' exists in Qdrant...")
        existing = [c.name for c in self.client.get_collections().collections]
        if self.collection_name in existing:
            logger.info(f"Collection '{self.collection_name}' already exists.")
            return

        logger.info(f"Creating collection '{self.collection_name}' with vector sizes: {self.vector_sizes}")
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config={
                "text_embedding": VectorParams(size=self.vector_sizes["text_embedding"], distance=self.distance),
                "image_embedding": VectorParams(size=self.vector_sizes["image_embedding"], distance=self.distance),
            }
        )
        logger.info(f"Collection '{self.collection_name}' created successfully.")

    def insert_document(
        self,
        text: Optional[str] = None,
        image: Optional[str] = None,
        metadata: Optional[dict] = None,
        id: Optional[int] = None,
        chunk: bool = False,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ):
        """
        Insert a document into the vector store. If chunk=True and text is provided,
        the text will be split into chunks using LangChain's RecursiveCharacterTextSplitter,
        and each chunk will be inserted as a separate point with its own id.
        """
        logger.debug(f"Preparing to insert document. Text provided: {bool(text)}, Image provided: {bool(image)}")
        if not text and not image:
            logger.error("Attempted to insert document without text or image.")
            raise ValueError("At least one of `text` or `image` must be provided.")

        # If chunking is enabled and text is provided, split and insert each chunk
        if chunk and text:
            logger.info("Chunking enabled. Splitting text into chunks for insertion.")
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap
            )
            chunks = text_splitter.split_text(text)
            logger.info(f"Text split into {len(chunks)} chunks.")

            for idx, chunk_text in enumerate(chunks):
                vectors = {}
                logger.debug("Generating text embedding for chunked document.")
                vectors["text_embedding"] = models.Document(text=chunk_text, model=self.text_embedding_model)
                if image:
                    logger.debug("Generating image embedding for document (applies to all chunks).")
                    vectors["image_embedding"] = models.Image(image=image, model=self.image_embedding_model)

                payload_data = metadata.copy() if metadata else {}
                payload_data["text"] = chunk_text
                if image:
                    payload_data["image"] = image
                payload_data["chunk_index"] = idx
                payload_data["chunk_count"] = len(chunks)

                point_id = (id or self._generate_id()) + idx
                logger.info(f"Inserting chunk {idx+1}/{len(chunks)} with id={point_id} into collection '{self.collection_name}'")
                point = PointStruct(
                    id=point_id,
                    vector=vectors,
                    payload=payload_data
                )

                try:
                    self.client.upsert(
                        collection_name=self.collection_name,
                        points=[point]
                    )
                    logger.info(f"Chunk {idx+1}/{len(chunks)} with id={point_id} inserted successfully.")
                except Exception as e:
                    logger.error(f"Failed to insert chunk {idx+1}/{len(chunks)} with id={point_id}: {e}")
                    raise
            return 

        vectors = {}
        if text:
            logger.debug("Generating text embedding for document.")
            vectors["text_embedding"] = models.Document(text=text, model=self.text_embedding_model)
        if image:
            logger.debug("Generating image embedding for document.")
            vectors["image_embedding"] = models.Image(image=image, model=self.image_embedding_model)

        payload_data = metadata.copy() if metadata else {}
        if text:
            payload_data["text"] = text
        if image:
            payload_data["image"] = image

        point_id = id or self._generate_id()
        logger.info(f"Inserting document with id={point_id} into collection '{self.collection_name}'")
        point = PointStruct(
            id=point_id,
            vector=vectors,
            payload=payload_data
        )

        try:
            self.client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )
            logger.info(f"Document with id={point_id} inserted successfully.")
        except Exception as e:
            logger.error(f"Failed to insert document with id={point_id}: {e}")
            raise

    def _generate_id(self):
        generated_id = int(time.time() * 1000)
        logger.debug(f"Generated new document id: {generated_id}")
        return generated_id
    
    def query(
        self,
        query_text: str,
        top_k: int = 3,
        using: str = "text_embedding",
    ):
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


if __name__ == "__main__":
    
    documents_dir = os.path.join(os.path.dirname(__file__), "documents")
    logger.info(f"Looking for PDF documents in directory: {documents_dir}")
    try:
        store = VectorStore("products-data")
        for filename in os.listdir(documents_dir):
            if filename.lower().endswith(".pdf"):
                pdf_path = os.path.join(documents_dir, filename)
                logger.info(f"Processing file: {filename}")
                try:
                    parser = PDFParser(pdf_path)
                    extracted_text = parser.extract_text()
                    logger.debug(f"Extracted text from {filename}: {extracted_text[:100]}..." if extracted_text else "No text extracted.")
             
                    store.insert_document(
                        text=extracted_text,
                        metadata={"source": filename},
                        chunk=True,
                        chunk_size=1000,  
                        chunk_overlap=200
                    )
                    logger.info(f"Inserted document from {filename} (with chunking)")
                except FileNotFoundError as e:
                    logger.error(f"File not found: {e}")
                    logger.error(f"Please ensure the PDF file '{filename}' exists in the 'documents' folder.")
                except Exception as e:
                    logger.error(f"Error processing {filename}: {e}")
   
        results = store.query("what did he do in Morgan Stanley?", 3)
        logger.info(f"Query results: {results}")
        print(results)
    except Exception as e:
        logger.critical(f"Fatal error: {e}")