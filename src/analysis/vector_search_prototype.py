import json
import os
import chromadb
from sentence_transformers import SentenceTransformer

# pip install -U huggingface_hub hf_transfer
# export HF_ENDPOINT=https://hf-mirror.com
# echo 'export HF_ENDPOINT=https://hf-mirror.com' >> ~/.bashrc
# source ~/.bashrc
# huggingface-cli download \
#   --resume-download \
#   --local-dir-use-symlinks False \
#   sentence-transformers/all-MiniLM-L6-v2 \
#   --local-dir /home.kai/models/all-MiniLM-L6-v2

def create_vector_database(file_path, sample_size=500):
    """
    Creates a vector database from a sample of structured event data.

    Args:
        file_path (str): Path to the JSONL file.
        sample_size (int): Number of records to sample.

    Returns:
        chromadb.Collection: The ChromaDB collection object.
    """
    print("Loading sentence transformer model...")
    # Using a multilingual model suitable for the data
    model = SentenceTransformer('all-MiniLM-L6-v2',cache_folder='/home/kai/models')
    print("Model loaded.")

    client = chromadb.Client()
    # Using a temporary in-memory collection for this prototype
    collection = client.create_collection(name="event_descriptions")

    documents = []
    metadatas = []
    ids = []

    print(f"Reading and processing {sample_size} records from {file_path}...")
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        if len(lines) < sample_size:
            sample_size = len(lines)
        sampled_lines = lines[:sample_size] # Take the first N for deterministic results

    for i, line in enumerate(sampled_lines):
        try:
            event = json.loads(line)
            description = event.get('description')
            event_type = event.get('event_type', 'N/A')
            
            if description:
                documents.append(description)
                metadatas.append({"event_type": event_type, "line_num": i + 1})
                ids.append(str(i))
        except (json.JSONDecodeError, AttributeError):
            continue
    
    if not documents:
        print("No valid documents found to process.")
        return None

    print(f"Generating embeddings for {len(documents)} documents...")
    embeddings = model.encode(documents)
    print("Embeddings generated.")

    print("Adding documents to ChromaDB collection...")
    collection.add(
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )
    print("Documents added successfully.")
    
    return collection

def perform_similarity_search(collection, query_text, n_results=5):
    """
    Performs a similarity search on the vector database.

    Args:
        collection (chromadb.Collection): The ChromaDB collection.
        query_text (str): The text to search for.
        n_results (int): The number of results to return.
    """
    if not collection:
        print("Collection is not available for searching.")
        return

    print(f"\n--- Performing similarity search for query: '{query_text}' ---")
    
    # The model needs to be loaded again for encoding the query
    model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    query_embedding = model.encode([query_text])
    
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=n_results,
    )
    
    print("Top 5 similar event descriptions:")
    for i, doc in enumerate(results['documents'][0]):
        distance = results['distances'][0][i]
        metadata = results['metadatas'][0][i]
        print(f"  {i+1}. (Distance: {distance:.4f}) (Type: {metadata.get('event_type')}) - \"{doc}\"")
    print("----------------------------------------------------")


if __name__ == "__main__":
    if not os.path.exists('src/analysis'):
        os.makedirs('src/analysis')
        
    data_file = 'output/extraction/structured_events.jsonl'
    
    # 1. Create the vector database from a sample of the data
    event_collection = create_vector_database(data_file)
    
    # 2. Perform a sample query
    if event_collection:
        sample_query = "华为发布新的芯片技术"
        perform_similarity_search(event_collection, sample_query)
