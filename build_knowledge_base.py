"""
Build the RAG knowledge base from documents in data/docs/.
Run once at setup, or whenever policy documents are updated.

Usage:
    python build_knowledge_base.py
"""
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from tools.rag_tool import build_knowledge_base

if __name__ == "__main__":
    print("=" * 50)
    print("  WhatsApp AI Agent — Build Knowledge Base")
    print("=" * 50)

    docs_dir = Path("data/docs")

    if not docs_dir.exists():
        print("\n❌ data/docs/ directory not found.")
        sys.exit(1)

    txt_files = list(docs_dir.glob("**/*.txt"))
    if not txt_files:
        print("\n❌ No .txt files found in data/docs/")
        sys.exit(1)

    print(f"\n📂 Found {len(txt_files)} document(s) in data/docs/:")
    for f in txt_files:
        print(f"   - {f.name} ({f.stat().st_size:,} bytes)")

    print("\n⏳ Building knowledge base...")
    count = build_knowledge_base()

    if count > 0:
        print(f"\n✅ Done! {count} chunks indexed and ready for search.")
        print("🚀 You can now start the server: python main.py")
    else:
        print("\n⚠️  No chunks were created. Check your documents.")
        sys.exit(1)