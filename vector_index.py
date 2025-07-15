from typing import List
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer, CrossEncoder
from sqlalchemy.orm import Session
from tqdm import tqdm
from models import TorrentFile, Video  # your updated model
import torch
from FlagEmbedding import FlagReranker


from functools import lru_cache

# Memoize by video id (not the object itself, to avoid memory leaks)
_document_text_cache = {}

print("Torch information:")
print(torch.version.cuda)          # Should print a CUDA version, e.g. '11.8'
print(torch.cuda.is_available())   # Should be True
print(torch.cuda.device_count())   # Number of GPUs detected
print(torch.cuda.get_device_name(0))  # GPU name
device = "cuda" if torch.cuda.is_available() else "cpu"

# Model:
# BAAI/bge-large-en-v1.5
# query_preamble = "Represent this sentence for searching relevant passages: "
# Qwen/Qwen3-Embedding-0.6B -> bad
# 'intfloat/e5-large-v2' -> bad


_model = None
query_preamble = "Represent this sentence for searching features: "
embedding_preamble = "Represent this sentence for semantic similarity:\n"
embedding_dim = 768
def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("jeonseonjin/embedding_BAAI-bge-m3", device=device, model_kwargs={"torch_dtype": "float16"})
    return _model

# FAISS is rebuilt from scratch each time, so it starts empty
faiss_index = faiss.IndexFlatIP(embedding_dim)
sqlite_id_lookup = []

def get_preamble():
    return query_preamble

# Load the reranker model (same as Hugging Face name)
# reranker = CrossEncoder("BAAI/bge-reranker-base", max_length=1024, model_kwargs={"torch_dtype": "float16"})

reranker = FlagReranker('BAAI/bge-reranker-v2-m3', use_fp16=True)
# "cross-encoder/ms-marco-MiniLM-L6-v2"
def rerank(query: str, documents: list[str]) -> list[tuple[str, float]]:
    pairs = [(query, doc) for doc in documents]

    total_bytes = sum(len(doc.encode('utf-8')) for doc in documents)

    # Get relevance scores
    # scores = reranker.predict(pairs, show_progress_bar=True)
    scores = reranker.compute_score(pairs, normalize=True)

    # Zip and sort
    ranked = sorted(zip(documents, scores), key=lambda x: x[1], reverse=True)

    # Print results
    for doc, score in ranked[:20]:
        print(f"{score:.2f}: {doc[:30]}")

    return ranked

def get_document_text_for_video(video: Video) -> str:
    if video.id in _document_text_cache:
        return _document_text_cache[video.id]
    
    text = "Filename: " + video.filename + "\n\n"

    if video.torrent_tags:
        text += "Tags: " + ", ".join(video.torrent_tags).replace('.', ' ') + "\n\n"
    
    # Collect filename metadata tags
    if video.filename_metadata:
        if video.filename_metadata.get('actors'):
            text += "Actors: " + ", ".join(video.filename_metadata['actors']) + "\n\n"
        
        if video.filename_metadata.get('series'):
            text += "Series: " + video.filename_metadata['series'] + "\n\n"
        
        if video.filename_metadata.get('scene_name'):
            text += "Scene Name: " + video.filename_metadata['scene_name'] + "\n\n"

        if video.filename_metadata.get('tags'):
            text += "Extra tags: " + ", ".join(video.filename_metadata['tags']) + "\n\n"

    # Collect tags from snapshot classification
    if video.tag_sets and video.tag_sets[0].tags:
            text += "Visual tags: " + ', '.join(video.tag_sets[0].tags) + "\n\n"

    if video.torrent_file and video.torrent_file.torrent and video.torrent_file.torrent.description:
        # Collect tags from torrent metadata
        text += "Description: " + video.torrent_file.torrent.description[:512] + "\n\n"

    _document_text_cache[video.id] = text
    return text

def generate_embeddings(videos: List[Video]) -> list[np.ndarray]:
    # Flatten all tags into a list of concatenated tag strings, one per VideoTagSet
    texts = [embedding_preamble + get_document_text_for_video(video) for video in tqdm(videos)]

    # Encode all tag texts in one batch
    embeddings = get_model().encode(texts, normalize_embeddings=True, convert_to_tensor=False, show_progress_bar=True)
    embeddings = [vec.astype('float32') for vec in embeddings]  # Ensure float32 type for FAISS
    return embeddings

def load_faiss_index(session: Session):
    global faiss_index, sqlite_id_lookup
    
    videos = session.query(Video).filter(
        Video.filename_metadata != None,
        Video.tag_sets != None
    ).all()
    embeddings = generate_embeddings(videos)
    if not embeddings:
        return

    # Re-initialize the FAISS index and lookup list
    embedding_dim = embeddings[0].shape[0]
    faiss_index = faiss.IndexFlatIP(embedding_dim)
    sqlite_id_lookup = []
    for video, vec in zip(videos, embeddings):
        faiss_index.add(np.array([vec]))
        sqlite_id_lookup.append(video.id)

def search_similar_from_video(session: Session, video: Video, k: int = 5) -> List[Video]:
    faiss_id = sqlite_id_lookup.index(video.id)
    query_vec = faiss_index.reconstruct(faiss_id).reshape(1, -1)
    return search_similar_from_vector(session, query_vec, k)

def search_similar_from_tags(session: Session, query_tags: list[str], k: int = 5) -> List[Video]:
    text = ', '.join(query_tags)
    query_vec = get_model().encode([text], normalize_embeddings=True)[0].astype('float32').reshape(1, -1)
    return search_similar_from_vector(session, query_vec, k)

def search_similar_from_string(session: Session, queries: list[str], k: int = 5, rerank_enabled: bool = True) -> List[Video]:
    # Generate query embeddings
    search_query_text = [query_preamble + query for query in queries]
    query_vec = get_model().encode(search_query_text, normalize_embeddings=True) #[0].astype('float32').reshape(1, -1)
    query_embedding = np.mean(query_vec, axis=0)
    
    # Search for similar videos using FAISS
    candidate_k = max(k * 5, 50)
    if not rerank_enabled:
        candidate_k = k
    candidate_videos = search_similar_from_vector(session, query_embedding, k=candidate_k)

    if not candidate_videos:
        return []
    
    if not rerank_enabled:
        return candidate_videos

    video_map = {get_document_text_for_video(v): v for v in candidate_videos}
    documents_to_rerank = list(video_map.keys())

    # 3. Rerank the documents
    reranked_docs = rerank(', '.join(queries), documents_to_rerank)

    # 4. Map reranked documents back to Video objects and truncate to original k
    final_results = [video_map[doc] for doc, score in reranked_docs if doc in video_map]
    
    return final_results[:k]
    # query = "Represent this sentence for searching relevant passages: " + query
    # query_vec = get_model().encode([query])[0].astype('float32').reshape(1, -1)
    # return search_similar_from_vector(session, query_vec, k)

def search_similar_from_vector(session: Session, query_vec: np.ndarray, k: int = 5, distance_threshold: float = None) -> List[Video]:
    # # Normalize the query vector
    # norm = np.linalg.norm(query_vec)
    # if norm > 0:
    #     query_vec = query_vec / norm

    # Ensure query_vec is 2D
    if query_vec.ndim == 1:
        query_vec = query_vec.reshape(1, -1)
    
    D, I = faiss_index.search(query_vec, k)

    results: list[Video] = []
    mindist = float('inf')
    maxdist = float('-inf')
    video_ids = []
    for dist, faiss_idx in zip(D[0], I[0]):
        if faiss_idx < len(sqlite_id_lookup):
            if dist < mindist:
                mindist = dist
            if dist > maxdist:
                maxdist = dist
            if distance_threshold is not None and dist < distance_threshold:
                continue  # Skip results that are too far away
            video_id = sqlite_id_lookup[faiss_idx]
            video_ids.append(video_id)
            # video = session.get(Video, video_id)
            # if video:
            #     results.append(video)
    
    # Eager-load relationships if needed
    from sqlalchemy.orm import joinedload
    videos = (
        session.query(Video)
        .filter(Video.id.in_(video_ids))
        .options(
            joinedload(Video.torrent_file).joinedload(TorrentFile.torrent),
            joinedload(Video.tag_sets)
        )
        .all()
    )

    video_map = {v.id: v for v in videos}

    # Preserve order and filter out missing
    results = [video_map[vid] for vid in video_ids if vid in video_map]

    print(f"Search results: {len(results)} videos found, distances range from {mindist:.4f} to {maxdist:.4f}")
    return results