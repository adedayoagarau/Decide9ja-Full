
import argparse
import sys
import logging
from app.services.document_ingester import ingest_pdf, ingest_url
from app.database import init_db

logging.basicConfig(level=logging.INFO)

def main():
    parser = argparse.ArgumentParser(description="Ingest documents into Decide9ja RAG")
    parser.add_argument("source", help="Path to PDF file or URL")
    parser.add_argument("--type", choices=["pdf", "url"], help="Type of source (auto-detected if omitted)")
    parser.add_argument("--title", help="Title of the document")
    parser.add_argument("--category", default="policy", help="Category (policy, law, report)")
    
    args = parser.parse_args()
    
    # Init DB
    init_db()
    
    source = args.source
    doc_type = args.type
    
    # Auto-detect type
    if not doc_type:
        if source.lower().startswith("http"):
            doc_type = "url"
        else:
            doc_type = "pdf"
            
    print(f"Ingesting {doc_type.upper()}: {source}...")
    
    try:
        if doc_type == "pdf":
            result = ingest_pdf(source, title=args.title, category=args.category)
        else:
            result = ingest_url(source, title=args.title, category=args.category)
            
        print(f"Success! {result}")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
