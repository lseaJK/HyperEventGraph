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
        It loads a local sentence-transformers model based on the configuration.
        """
        config = get_config()
        vectorizer_config = config.get('cortex', {}).get('vectorizer', {})
        model_type = vectorizer_config.get('model_type')
        
        if model_type != 'local':
            raise ValueError(f"VectorizationService currently only supports 'local' model_type, but found '{model_type}'")
            
        model_name = vectorizer_config.get('model_name')
        if not model_name:
            raise ValueError("model_name not specified in config for local vectorizer.")

        # Load the local sentence-transformers model
        # The model will be downloaded from HuggingFace and cached locally the first time.
        print(f"Initializing VectorizationService with local model: {model_name}")
        self.model = SentenceTransformer(model_name)
        print("VectorizationService initialized successfully.")

    def get_embedding(self, text: str) -> list[float]:
        """
        Generates an embedding for a single piece of text.

        Args:
            text: The input string to embed.

        Returns:
            A list of floats representing the vector embedding.
        """
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        Generates embeddings for a batch of texts.

        Args:
            texts: A list of input strings to embed.

        Returns:
            A list of vector embeddings.
        """
        print(f"Generating embeddings for a batch of {len(texts)} texts using local model...")
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        print("Embeddings generated successfully.")
        return embeddings.tolist()

def main_test():
    """A simple function to test the service."""
    # This requires the config to be loaded first.
    # from src.core.config_loader import load_config
    # load_config("config.yaml")
    
    print("Running VectorizationService test...")
    service = VectorizationService()
    texts = [
        "This is a test sentence.",
        "Here is another one, quite different."
    ]
    embeddings = service.get_embeddings(texts)
    print(f"Generated {len(embeddings)} embeddings.")
    for i, emb in enumerate(embeddings):
        print(f"  Embedding {i+1}: Dimension={len(emb)}")

if __name__ == '__main__':
    # To run this test properly, you need to ensure the config is loaded.
    # For example, by running it from a script that calls load_config() first.
    print("This script is not meant to be run directly without a proper setup.")
    # Example of how to run the test:
    # from src.core.config_loader import load_config
    # from pathlib import Path
    # config_path = Path(__file__).resolve().parents[2] / "config.yaml"
    # load_config(config_path)
    # main_test()
    pass
