import os
from dotenv import load_dotenv

load_dotenv()

class Config:
 
    # Qdrant Config
    QDRANT_URL = os.getenv('QDRANT_URL')
    QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')
    
    TEXT_EMBEDDING_MODEL = os.getenv("TEXT_EMBEDDING_MODEL")
    IMAGE_EMBEDDING_MODEL = os.getenv("IMAGE_EMBEDDING_MODEL")

    COLLECTION_NAME = "products-data"
    METADATA_FILE = r"C:\Users\subar\OneDrive\Desktop\capitalone\agents\tools\utils\all_metadata.json"
    
if __name__ == "__main__":
  
    print(Config.QDRANT_API_KEY)
    print(Config.QDRANT_URL)