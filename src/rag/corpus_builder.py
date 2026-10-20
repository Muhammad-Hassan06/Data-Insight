"""
Corpus Builder for RAG Insight Agent
Chunks PDF documents and builds a persistent vector database using ChromaDB.
"""

import os
from pathlib import Path
from typing import List, Dict
import pdfplumber
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings


class CorpusBuilder:
    """Builds a searchable corpus from PDF documents."""
    
    def __init__(self, corpus_dir: str = "corpus", db_dir: str = "corpus/chroma_db"):
        """
        Initialize the corpus builder.
        
        Args:
            corpus_dir: Directory containing PDF files
            db_dir: Directory for persistent ChromaDB storage
        """
        self.corpus_dir = Path(corpus_dir)
        self.db_dir = Path(db_dir)
        
        # Create ChromaDB client with persistent storage
        self.client = chromadb.PersistentClient(
            path=str(self.db_dir),
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name="air_quality_documents",
            metadata={"description": "Trusted sources on air quality and PM2.5"}
        )
        
        # Initialize sentence transformer for embeddings
        print("Loading sentence transformer model...")
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
        print("Model loaded successfully.")
    
    def chunk_document(self, pdf_path: Path, chunk_size: int = 500, overlap: int = 50) -> List[Dict]:
        """
        Extract text from PDF and split into overlapping chunks.
        
        Args:
            pdf_path: Path to PDF file
            chunk_size: Approximate number of characters per chunk
            overlap: Number of characters to overlap between chunks
            
        Returns:
            List of chunks with metadata
        """
        chunks = []
        
        print(f"Processing {pdf_path.name}...")
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    text = page.extract_text()
                    
                    if not text:
                        continue
                    
                    # Clean the text
                    text = text.strip()
                    text = " ".join(text.split())  # Normalize whitespace
                    
                    # Split into chunks with overlap
                    start = 0
                    while start < len(text):
                        end = start + chunk_size
                        chunk_text = text[start:end]
                        
                        # Only keep non-empty chunks with reasonable length
                        if len(chunk_text.strip()) > 50:
                            chunks.append({
                                "text": chunk_text,
                                "source": pdf_path.name,
                                "page": page_num,
                                "char_start": start,
                                "char_end": min(end, len(text))
                            })
                        
                        start = end - overlap
                        
                        # Break if we've reached the end
                        if end >= len(text):
                            break
        
        except Exception as e:
            print(f"Error processing {pdf_path.name}: {e}")
            return []
        
        print(f"  Created {len(chunks)} chunks from {pdf_path.name}")
        return chunks
    
    def build_corpus(self, force_rebuild: bool = False) -> Dict:
        """
        Build the vector database from all PDFs in the corpus directory.
        
        Args:
            force_rebuild: If True, delete existing collection and rebuild
            
        Returns:
            Summary statistics
        """
        # Check if collection already has documents
        existing_count = self.collection.count()
        
        if existing_count > 0 and not force_rebuild:
            print(f"Collection already contains {existing_count} documents.")
            print("Use force_rebuild=True to rebuild from scratch.")
            return {
                "status": "skipped",
                "existing_documents": existing_count,
                "message": "Collection already built"
            }
        
        if force_rebuild and existing_count > 0:
            print(f"Deleting existing collection with {existing_count} documents...")
            self.client.delete_collection("air_quality_documents")
            self.collection = self.client.create_collection(
                name="air_quality_documents",
                metadata={"description": "Trusted sources on air quality and PM2.5"}
            )
        
        # Find all PDF files
        pdf_files = list(self.corpus_dir.glob("*.pdf"))
        
        if not pdf_files:
            print(f"No PDF files found in {self.corpus_dir}")
            return {
                "status": "error",
                "message": "No PDF files found"
            }
        
        print(f"\nFound {len(pdf_files)} PDF files")
        print("=" * 60)
        
        # Process all PDFs
        all_chunks = []
        for pdf_path in pdf_files:
            chunks = self.chunk_document(pdf_path)
            all_chunks.extend(chunks)
        
        if not all_chunks:
            print("No content extracted from PDFs")
            return {
                "status": "error",
                "message": "No content extracted"
            }
        
        print(f"\nTotal chunks: {len(all_chunks)}")
        print("Adding to ChromaDB...")
        
        # Add to ChromaDB in batches
        batch_size = 100
        for i in range(0, len(all_chunks), batch_size):
            batch = all_chunks[i:i + batch_size]
            
            documents = [chunk["text"] for chunk in batch]
            metadatas = [
                {
                    "source": chunk["source"],
                    "page": chunk["page"],
                    "char_start": chunk["char_start"],
                    "char_end": chunk["char_end"]
                }
                for chunk in batch
            ]
            ids = [f"{chunk['source']}_p{chunk['page']}_{chunk['char_start']}" for chunk in batch]
            
            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            
            print(f"  Added batch {i // batch_size + 1}/{(len(all_chunks) - 1) // batch_size + 1}")
        
        final_count = self.collection.count()
        
        print("\n" + "=" * 60)
        print(f"✓ Corpus built successfully!")
        print(f"  Total documents in collection: {final_count}")
        print(f"  Storage location: {self.db_dir}")
        
        return {
            "status": "success",
            "total_documents": final_count,
            "pdf_files_processed": len(pdf_files),
            "storage_path": str(self.db_dir)
        }
    
    def get_stats(self) -> Dict:
        """Get statistics about the current corpus."""
        count = self.collection.count()
        
        if count == 0:
            return {
                "total_documents": 0,
                "message": "Collection is empty"
            }
        
        # Sample a few documents to get source distribution
        sample = self.collection.get(limit=min(count, 100))
        sources = {}
        
        for metadata in sample['metadatas']:
            source = metadata.get('source', 'unknown')
            sources[source] = sources.get(source, 0) + 1
        
        return {
            "total_documents": count,
            "sources": sources,
            "storage_path": str(self.db_dir)
        }


def main():
    """Build the corpus from command line."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Build RAG corpus from PDF files")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Force rebuild even if corpus exists"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show statistics about existing corpus"
    )
    
    args = parser.parse_args()
    
    builder = CorpusBuilder()
    
    if args.stats:
        stats = builder.get_stats()
        print("\nCorpus Statistics:")
        print("=" * 60)
        for key, value in stats.items():
            print(f"{key}: {value}")
    else:
        result = builder.build_corpus(force_rebuild=args.rebuild)
        
        if result["status"] == "success":
            print("\n✓ Ready to use with query_agent.py")
        elif result["status"] == "skipped":
            print("\n✓ Corpus already exists. Use --rebuild to recreate.")
        else:
            print(f"\n✗ Error: {result['message']}")


if __name__ == "__main__":
    main()
