import os
import json
import logging
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from django.conf import settings

logger = logging.getLogger(__name__)

class VectorService:
    _model = None
    INDEX_PATH = os.path.join(settings.DATA_DIR, "candidates.index")
    MAPPING_PATH = os.path.join(settings.DATA_DIR, "faiss_mapping.json")

    @classmethod
    def get_model(cls):
        """
        Lazy loader for the SentenceTransformer model.
        """
        if cls._model is None:
            logger.info("Initializing SentenceTransformer model 'all-MiniLM-L6-v2'...")
            cls._model = SentenceTransformer("all-MiniLM-L6-v2")
        return cls._model

    @classmethod
    def save_mapping(cls, mapping):
        with open(cls.MAPPING_PATH, 'w') as f:
            json.dump(mapping, f)

    @classmethod
    def load_mapping(cls):
        if not os.path.exists(cls.MAPPING_PATH):
            return []
        with open(cls.MAPPING_PATH, 'r') as f:
            try:
                return json.load(f)
            except Exception as e:
                logger.error(f"Error loading FAISS mapping: {str(e)}")
                return []

    @classmethod
    def add_candidate(cls, candidate_id, text_to_embed):
        """
        Generates embedding and appends to the FAISS index.
        """
        try:
            candidate_id_str = str(candidate_id)
            logger.info(f"Adding candidate {candidate_id_str} to Vector index.")
            
            # Generate embedding
            model = cls.get_model()
            vector = model.encode([text_to_embed])[0]
            vector = np.array([vector]).astype('float32')
            dimension = vector.shape[1]

            # Load or create index
            if os.path.exists(cls.INDEX_PATH):
                index = faiss.read_index(cls.INDEX_PATH)
            else:
                logger.info(f"Creating new FAISS index with dimension {dimension}")
                index = faiss.IndexFlatL2(dimension)

            # Add to FAISS index
            index.add(vector)
            faiss.write_index(index, cls.INDEX_PATH)

            # Update mapping
            mapping = cls.load_mapping()
            # If candidate already exists, we could replace it, but for simplicity we append.
            # (In production, checking/removing duplicate IDs before appending is standard).
            mapping.append(candidate_id_str)
            cls.save_mapping(mapping)
            
            logger.info(f"Successfully added candidate {candidate_id_str} to Vector DB.")
        except Exception as e:
            logger.error(f"Failed to add candidate to FAISS index: {str(e)}")

    @classmethod
    def search_candidates(cls, query, top_k=5):
        """
        Queries FAISS for matching vectors and returns the corresponding Candidate UUIDs.
        """
        if not os.path.exists(cls.INDEX_PATH) or not os.path.exists(cls.MAPPING_PATH):
            logger.warning("FAISS index or mapping file does not exist. Returning empty results.")
            return []

        try:
            logger.info(f"Searching vector database for: '{query}'")
            model = cls.get_model()
            query_vector = model.encode([query])[0]
            query_vector = np.array([query_vector]).astype('float32')

            index = faiss.read_index(cls.INDEX_PATH)
            mapping = cls.load_mapping()

            # Search L2 distance
            distances, indices = index.search(query_vector, min(top_k, len(mapping)))
            
            candidate_ids = []
            for idx in indices[0]:
                if idx != -1 and idx < len(mapping):
                    candidate_ids.append(mapping[idx])

            logger.info(f"Found {len(candidate_ids)} candidates matching vector query.")
            return candidate_ids
        except Exception as e:
            logger.error(f"Error searching FAISS index: {str(e)}")
            return []
