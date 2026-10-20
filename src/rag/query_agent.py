"""
Query Agent for RAG-based PM2.5 Insights
Provides cited answers from trusted sources with data warehouse integration.
"""

from typing import Dict, List, Optional
from datetime import datetime
import chromadb
from chromadb.config import Settings
import duckdb
from pathlib import Path


class InsightAgent:
    """RAG agent that provides cited answers from trusted sources."""
    
    def __init__(
        self,
        db_path: str = "data/processed/warehouse.duckdb",
        chroma_path: str = "corpus/chroma_db"
    ):
        """
        Initialize the Insight Agent.
        
        Args:
            db_path: Path to DuckDB warehouse
            chroma_path: Path to ChromaDB corpus
        """
        self.db_path = Path(db_path)
        self.chroma_path = Path(chroma_path)
        
        # Connect to ChromaDB
        if not self.chroma_path.exists():
            raise FileNotFoundError(
                f"ChromaDB not found at {chroma_path}. "
                "Run corpus_builder.py first to build the corpus."
            )
        
        self.chroma_client = chromadb.PersistentClient(
            path=str(self.chroma_path),
            settings=Settings(anonymized_telemetry=False)
        )
        
        try:
            self.collection = self.chroma_client.get_collection("air_quality_documents")
            print(f"✓ Connected to corpus ({self.collection.count()} documents)")
        except Exception as e:
            raise RuntimeError(f"Failed to load corpus collection: {e}")
        
        # Connect to DuckDB (lazy connection)
        self.db_conn = None
        if self.db_path.exists():
            self.db_conn = duckdb.connect(str(self.db_path), read_only=True)
            print(f"✓ Connected to warehouse: {self.db_path}")
        else:
            print(f"⚠ Warehouse not found at {self.db_path}")
    
    def retrieve_context(self, question: str, n_results: int = 3) -> Dict:
        """
        Retrieve relevant document chunks for a question.
        
        Args:
            question: User's question
            n_results: Number of relevant chunks to retrieve
            
        Returns:
            Dictionary with documents, metadatas, distances
        """
        results = self.collection.query(
            query_texts=[question],
            n_results=n_results
        )
        
        return {
            "documents": results["documents"][0] if results["documents"] else [],
            "metadatas": results["metadatas"][0] if results["metadatas"] else [],
            "distances": results["distances"][0] if results["distances"] else []
        }
    
    def query_gold_table(
        self,
        city: Optional[str] = None,
        date: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100
    ) -> Optional[Dict]:
        """
        Query the gold forecast features table.
        
        Args:
            city: City name (Lahore, Karachi, Islamabad, Peshawar)
            date: Specific date (YYYY-MM-DD)
            start_date: Start of date range (YYYY-MM-DD)
            end_date: End of date range (YYYY-MM-DD)
            limit: Maximum rows to return
            
        Returns:
            Dictionary with data and metadata, or None if no data
        """
        if self.db_conn is None:
            return None
        
        try:
            # Build query
            conditions = []
            
            if city:
                conditions.append(f"city = '{city}'")
            
            if date:
                conditions.append(f"DATE(timestamp) = '{date}'")
            elif start_date and end_date:
                conditions.append(f"DATE(timestamp) BETWEEN '{start_date}' AND '{end_date}'")
            elif start_date:
                conditions.append(f"DATE(timestamp) >= '{start_date}'")
            elif end_date:
                conditions.append(f"DATE(timestamp) <= '{end_date}'")
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            query = f"""
                SELECT 
                    row_id,
                    city,
                    timestamp_utc,
                    pm25_ugm3 as pm25_value
                FROM gold_forecast_features
                WHERE {where_clause}
                ORDER BY timestamp_utc DESC
                LIMIT {limit}
            """
            
            result = self.db_conn.execute(query).fetchdf()
            
            if result.empty:
                return None
            
            return {
                "data": result,
                "row_ids": result["row_id"].tolist(),
                "count": len(result),
                "date_range": {
                    "start": str(result["timestamp_utc"].min()),
                    "end": str(result["timestamp_utc"].max())
                }
            }
        
        except Exception as e:
            print(f"Error querying database: {e}")
            return None
    
    def _format_citations(self, metadatas: List[Dict]) -> str:
        """Format citation metadata into readable text."""
        if not metadatas:
            return ""
        
        citations = []
        seen_sources = set()
        
        for meta in metadatas:
            source = meta.get("source", "unknown")
            if source not in seen_sources:
                page = meta.get("page", "?")
                citations.append(f"{source} (p.{page})")
                seen_sources.add(source)
        
        return ", ".join(citations)
    
    def generate_answer(self, question: str) -> Dict:
        """
        Generate an answer to a question using RAG and data warehouse.
        
        Args:
            question: User's question
            
        Returns:
            Dictionary with answer, citations, and row_ids
        """
        question_lower = question.lower()
        
        # Retrieve relevant document context
        context = self.retrieve_context(question, n_results=3)
        
        # Check relevance - if all documents have high distance, they're not relevant
        # ChromaDB uses L2 distance - lower is better, typically < 1.0 is relevant
        if context["distances"] and all(d > 1.5 for d in context["distances"]):
            # No relevant documents found
            return {
                "answer": "I don't know. I don't have information about that in my trusted sources or data warehouse.",
                "citations": [],
                "row_ids": [],
                "data_points": 0
            }
        
        # Check if question is about air quality topics
        air_quality_terms = ["pm2.5", "pm 2.5", "air quality", "pollution", "aqi", 
                            "smog", "particulate", "lahore", "karachi", "islamabad", 
                            "peshawar", "pakistan", "who", "epa", "health", "guideline"]
        
        is_relevant = any(term in question_lower for term in air_quality_terms)
        
        if not is_relevant and not context["documents"]:
            return {
                "answer": "I don't know. I don't have information about that in my trusted sources or data warehouse.",
                "citations": [],
                "row_ids": [],
                "data_points": 0
            }
        
        # Check if question is asking for specific data
        data_query = None
        
        # Extract city from question
        cities = ["lahore", "karachi", "islamabad", "peshawar"]
        mentioned_city = None
        for city in cities:
            if city in question_lower:
                mentioned_city = city.capitalize()
                break
        
        # Check for temporal references
        today_mentioned = any(word in question_lower for word in ["today", "current", "now", "latest"])
        
        # Try to query data if question seems data-related
        if any(term in question_lower for term in ["pm2.5", "pm 2.5", "air quality", "pollution level"]):
            if mentioned_city or today_mentioned:
                data_query = self.query_gold_table(city=mentioned_city, limit=24)
        
        # Case 1: Data-related question with available data
        if data_query is not None and data_query["count"] > 0:
            df = data_query["data"]
            
            # Calculate statistics
            mean_pm25 = df["pm25_value"].mean()
            max_pm25 = df["pm25_value"].max()
            min_pm25 = df["pm25_value"].min()
            
            city_str = f" in {mentioned_city}" if mentioned_city else ""
            
            # Build answer with data
            answer = f"Based on sensor data (row IDs: {data_query['row_ids'][:5]}), "
            
            if len(data_query["row_ids"]) > 5:
                answer += f"and {len(data_query['row_ids']) - 5} more rows), "
            
            answer += f"PM2.5 levels{city_str} averaged {mean_pm25:.1f} μg/m³ "
            answer += f"(range: {min_pm25:.1f} - {max_pm25:.1f} μg/m³). "
            
            # Add health interpretation from documents if available
            if context["documents"]:
                # Find most relevant context about health impacts
                for doc, meta in zip(context["documents"], context["metadatas"]):
                    if any(term in doc.lower() for term in ["health", "unhealthy", "sensitive", "guideline"]):
                        answer += f"\n\nAccording to {meta['source']} (p.{meta['page']}): "
                        answer += doc[:200] + "..."
                        break
            
            return {
                "answer": answer,
                "citations": context["metadatas"],
                "row_ids": data_query["row_ids"],
                "data_points": data_query["count"]
            }
        
        # Case 2: General knowledge question with document context
        elif context["documents"]:
            # Use the most relevant document
            best_doc = context["documents"][0]
            best_meta = context["metadatas"][0]
            
            answer = f"According to {best_meta['source']} (p.{best_meta['page']}): "
            answer += best_doc
            
            # Add supporting sources
            if len(context["documents"]) > 1:
                answer += f"\n\nAdditional sources: {self._format_citations(context['metadatas'][1:])}"
            
            return {
                "answer": answer,
                "citations": context["metadatas"],
                "row_ids": [],
                "data_points": 0
            }
        
        # Case 3: Cannot answer
        else:
            return {
                "answer": "I don't know. I don't have information about that in my trusted sources or data warehouse.",
                "citations": [],
                "row_ids": [],
                "data_points": 0
            }
    
    def ask(self, question: str) -> None:
        """
        Ask a question and print the formatted response.
        
        Args:
            question: User's question
        """
        print("\n" + "=" * 70)
        print(f"Question: {question}")
        print("=" * 70)
        
        response = self.generate_answer(question)
        
        print(f"\n{response['answer']}\n")
        
        if response['row_ids']:
            print(f"📊 Data points: {response['data_points']}")
            print(f"🔗 Row IDs: {response['row_ids'][:10]}")
            if len(response['row_ids']) > 10:
                print(f"   ... and {len(response['row_ids']) - 10} more")
        
        if response['citations']:
            print(f"\n📚 Sources:")
            for meta in response['citations']:
                print(f"   - {meta['source']} (page {meta['page']})")
        
        print("=" * 70)


def main():
    """Interactive CLI for the Insight Agent."""
    import argparse
    
    parser = argparse.ArgumentParser(description="RAG Insight Agent for PM2.5 Forecasting")
    parser.add_argument(
        "--question",
        type=str,
        help="Ask a single question and exit"
    )
    parser.add_argument(
        "--db",
        type=str,
        default="data/processed/warehouse.duckdb",
        help="Path to DuckDB warehouse"
    )
    parser.add_argument(
        "--corpus",
        type=str,
        default="corpus/chroma_db",
        help="Path to ChromaDB corpus"
    )
    
    args = parser.parse_args()
    
    # Initialize agent
    print("Initializing Insight Agent...")
    try:
        agent = InsightAgent(db_path=args.db, chroma_path=args.corpus)
    except Exception as e:
        print(f"✗ Failed to initialize agent: {e}")
        return
    
    # Single question mode
    if args.question:
        agent.ask(args.question)
        return
    
    # Interactive mode
    print("\n" + "=" * 70)
    print("RAG Insight Agent - Interactive Mode")
    print("=" * 70)
    print("Ask questions about air quality and PM2.5 forecasting.")
    print("Type 'exit' or 'quit' to end the session.\n")
    
    while True:
        try:
            question = input("❓ Your question: ").strip()
            
            if not question:
                continue
            
            if question.lower() in ["exit", "quit", "q"]:
                print("\nGoodbye!")
                break
            
            agent.ask(question)
            print()
        
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\n✗ Error: {e}\n")


if __name__ == "__main__":
    main()
