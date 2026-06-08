import os
from pathlib import Path

# Use updated non-deprecated packages
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

DOCS_DIR = Path(__file__).parent.parent / "data" / "docs"
DB_DIR   = Path(__file__).parent.parent / "data" / "vectordb"

# Embedding model: local, free, strong Arabic support
EMBEDDING_MODEL = "intfloat/multilingual-e5-large"
COLLECTION_NAME = "store_knowledge"


def _get_embeddings() -> HuggingFaceEmbeddings:
    """Load the local embedding model (cached after first load)."""
    return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)


def build_knowledge_base() -> int:
    """
    Read all .txt files from data/docs/, split into chunks,
    embed them and persist to ChromaDB.
    Run once at setup, or whenever docs are updated.
    """
    if not DOCS_DIR.exists():
        print("⚠️  data/docs/ directory not found")
        return 0

    loader = DirectoryLoader(
        str(DOCS_DIR),
        glob="**/*.txt",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
    )
    documents = loader.load()

    if not documents:
        print("⚠️  No .txt files found in data/docs/")
        return 0

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=60,
        # Ordered by priority: section breaks → paragraphs → sentences
        separators=["\n━", "\n\n", "\n", ".", "،", " "],
    )
    chunks = splitter.split_documents(documents)

    DB_DIR.mkdir(parents=True, exist_ok=True)

    Chroma.from_documents(
        documents=chunks,
        embedding=_get_embeddings(),
        persist_directory=str(DB_DIR),
        collection_name=COLLECTION_NAME,
    )

    print(f"✅ Knowledge base built: {len(chunks)} chunks from {len(documents)} file(s)")
    return len(chunks)


def search_knowledge(query: str, k: int = 3) -> str | None:
    """
    Search the vector store for chunks relevant to the query.
    Returns joined text of top results, or None if nothing is relevant.
    Relevance threshold: score >= 0.3
    """
    if not DB_DIR.exists():
        return None

    try:
        db = Chroma(
            persist_directory=str(DB_DIR),
            embedding_function=_get_embeddings(),
            collection_name=COLLECTION_NAME,
        )
        results = db.similarity_search_with_relevance_scores(query, k=k)
        relevant = [doc.page_content for doc, score in results if score >= 0.3]
        return "\n\n---\n\n".join(relevant) if relevant else None

    except Exception as e:
        print(f"⚠️  RAG search error: {e}")
        return None