# src/cortex/vectorization_service.py

from sentence_transformers import SentenceTransformer
from src.core.config_loader import get_config
import numpy as np

class VectorizationService:
    """
    Handles the conversion of text data into vector embeddings.
    This implementation uses a local sentence-transformers model.
    """

    def __init__(self):
        """
        Initializes the VectorizationService.
        It loads a local sentence-transformers model based on the configuration,
        using a centralized cache directory.
        """
        config = get_config()
        vectorizer_config = config.get('cortex', {}).get('vectorizer', {})
        model_type = vectorizer_config.get('model_type')
        
        if model_type != 'local':
            raise ValueError(f"VectorizationService currently only supports 'local' model_type, but found '{model_type}'")
            
        model_name = vectorizer_config.get('model_name')
        if not model_name:
            raise ValueError("model_name not specified in config for local vectorizer.")

        # Get the central model cache directory from the config
        cache_dir = config.get('model_settings', {}).get('cache_dir')
        if not cache_dir:
            print("Warning: 'model_settings.cache_dir' not found in config. Using default cache location.")

        print(f"Initializing VectorizationService with local model: {model_name}")
        print(f"Using cache directory: {cache_dir}")
        self.model = SentenceTransformer(model_name, cache_folder=cache_dir)
        print("VectorizationService initialized successfully.")

    def get_embedding(self, text: str) -> list[float]:
        """
        Generates an embedding for a single piece of text.
        """
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        Generates embeddings for a batch of texts.
        """
        print(f"Generating embeddings for a batch of {len(texts)} texts using local model...")
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        print("Embeddings generated successfully.")
        return embeddings.tolist()