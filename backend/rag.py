
import os
import pickle
import numpy as np
from typing import List, Dict, Any
from pathlib import Path
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

from .config import DATA_DIR

# Global embedding model instance (lazy loaded)
_embedding_model = None

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        # Use a small, fast model
        _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    return _embedding_model

class RAGEngine:
    def __init__(self):
        self.rag_dir = Path(DATA_DIR) / "rag"
        self.rag_dir.mkdir(parents=True, exist_ok=True)
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )

    def _get_conv_dir(self, conversation_id: str) -> Path:
        path = self.rag_dir / conversation_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _get_store_path(self, conversation_id: str) -> Path:
        return self._get_conv_dir(conversation_id) / "store.pkl"

    def process_file(self, conversation_id: str, file_content: bytes, filename: str) -> Dict[str, Any]:
        """
        Process an uploaded file: extract text, chunk, embed, and store.
        """
        # 1. Extract text
        text = ""
        if filename.lower().endswith('.pdf'):
            text = self._extract_pdf(file_content)
        else:
            # Assume text/md
            text = file_content.decode('utf-8', errors='ignore')

        if not text.strip():
            return {"error": "Empty file or could not extract text"}

        # 2. Split text
        chunks = self.text_splitter.split_text(text)
        
        # 3. Embed
        model = get_embedding_model()
        embeddings = model.encode(chunks)

        # 4. Update storage for this conversation
        store = self._load_store(conversation_id)
        
        # Structure: list of dicts {'text': str, 'embedding': np.array, 'source': filename}
        new_docs = []
        for i, chunk in enumerate(chunks):
            new_docs.append({
                "text": chunk,
                "embedding": embeddings[i],
                "source": filename
            })
            
        store["documents"].extend(new_docs)
        self._save_store(conversation_id, store)
        
        return {
            "filename": filename,
            "chunks_count": len(chunks),
            "total_docs": len(store["documents"])
        }

    def remove_file(self, conversation_id: str, filename: str) -> bool:
        """
        Remove a file and its associated chunks from the store.
        """
        store = self._load_store(conversation_id)
        if not store["documents"]:
            return False
            
        initial_count = len(store["documents"])
        # Filter out docs with matching source
        store["documents"] = [d for d in store["documents"] if d["source"] != filename]
        
        if len(store["documents"]) < initial_count:
            self._save_store(conversation_id, store)
            return True
            
        return False

    def search(self, conversation_id: str, query: str, k: int = 3) -> List[Dict[str, Any]]:
        """
        Search for relevant chunks in the conversation's documents.
        """
        store = self._load_store(conversation_id)
        if not store["documents"]:
            return []

        model = get_embedding_model()
        query_embedding = model.encode([query])[0]

        # Calculate similarities
        docs = store["documents"]
        scores = []
        for doc in docs:
            # Cosine similarity
            score = np.dot(query_embedding, doc["embedding"]) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(doc["embedding"])
            )
            scores.append((score, doc))

        # Sort by score desc
        scores.sort(key=lambda x: x[0], reverse=True)
        
        # Return top k
        results = []
        for score, doc in scores[:k]:
            results.append({
                "text": doc["text"],
                "source": doc["source"],
                "score": float(score)
            })
            
        return results

    def _load_store(self, conversation_id: str) -> Dict[str, Any]:
        path = self._get_store_path(conversation_id)
        if path.exists():
            try:
                with open(path, 'rb') as f:
                    return pickle.load(f)
            except Exception:
                return {"documents": []}
        return {"documents": []}

    def _save_store(self, conversation_id: str, store: Dict[str, Any]):
        path = self._get_store_path(conversation_id)
        with open(path, 'wb') as f:
            pickle.dump(store, f)

    def _extract_pdf(self, file_content: bytes) -> str:
        import io
        pdf = PdfReader(io.BytesIO(file_content))
        text = ""
        for page in pdf.pages:
            text += page.extract_text() + "\n"
        return text

# Global instance
rag_engine = RAGEngine()
