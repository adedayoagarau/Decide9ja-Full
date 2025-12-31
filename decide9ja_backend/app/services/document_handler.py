"""
Document Handler for Decide9ja.
Extracts and summarizes content from PDFs and documents.
Handles manifestos, bills, budget documents, etc.
"""
import os
import logging
import tempfile
import requests
from typing import Optional, Dict, List
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def is_configured() -> bool:
    """Check if document handler is configured."""
    # Requires PyPDF and Anthropic
    try:
        import pypdf
        return bool(os.getenv("ANTHROPIC_API_KEY"))
    except ImportError:
        return False


async def download_document(url: str, auth: tuple = None) -> Optional[bytes]:
    """Download document from URL."""
    try:
        headers = {}
        if auth:
            import base64
            credentials = base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
            headers["Authorization"] = f"Basic {credentials}"
        
        response = requests.get(url, headers=headers, timeout=60)
        response.raise_for_status()
        return response.content
    except Exception as e:
        logger.error(f"Failed to download document: {e}")
        return None


def extract_pdf_text(pdf_bytes: bytes, max_pages: int = 10) -> str:
    """Extract text from PDF bytes."""
    try:
        from pypdf import PdfReader
        import io
        
        pdf_file = io.BytesIO(pdf_bytes)
        reader = PdfReader(pdf_file)
        
        text_parts = []
        for i, page in enumerate(reader.pages[:max_pages]):
            page_text = page.extract_text()
            if page_text:
                text_parts.append(f"--- Page {i+1} ---\n{page_text}")
        
        full_text = "\n\n".join(text_parts)
        
        # Truncate if too long
        if len(full_text) > 15000:
            full_text = full_text[:15000] + "\n\n[Document truncated...]"
        
        return full_text
        
    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
        return ""


async def process_document(
    document_url: str,
    document_type: str = "unknown",
    user_question: str = ""
) -> Dict:
    """
    Process a document (PDF, etc.) and summarize/analyze it.
    
    Args:
        document_url: URL to document
        document_type: "manifesto", "bill", "budget", "letter", or "unknown"
        user_question: Optional specific question about the document
        
    Returns:
        Dict with extracted text, summary, and key points
    """
    try:
        from anthropic import Anthropic
        
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return {"error": "API key not configured"}
        
        client = Anthropic(api_key=api_key)
        
        # Download document from Twilio
        twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
        twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
        
        doc_bytes = await download_document(document_url, auth=(twilio_sid, twilio_token))
        
        if not doc_bytes:
            return {"error": "Failed to download document"}
        
        # Extract text
        text = extract_pdf_text(doc_bytes)
        
        if not text:
            return {"error": "Could not extract text from document"}
        
        # Build analysis prompt
        prompts = {
            "manifesto": """Analyze this political party manifesto:
1. Which party is this for?
2. List the TOP 5 key promises in bullet points
3. What are the main policy areas covered?
4. Any notable or controversial points?

Keep summary under 200 words. Be objective.""",
            
            "bill": """Analyze this legislative bill:
1. What is the bill about?
2. Who sponsored it?
3. What would it change if passed?
4. Who does it affect?

Summarize in simple terms for citizens.""",
            
            "budget": """Analyze this budget document:
1. What is the total amount?
2. What are the biggest spending areas?
3. Any allocations for roads, education, healthcare?
4. Any concerns or notable items?

Summarize key numbers.""",
            
            "unknown": """Analyze this document:
1. What type of document is this?
2. What is the main content/purpose?
3. Key points or takeaways?
4. Who should care about this?

Summarize concisely."""
        }
        
        base_prompt = prompts.get(document_type, prompts["unknown"])
        
        if user_question:
            base_prompt += f"\n\nUser's specific question: {user_question}"
        
        full_prompt = f"{base_prompt}\n\n--- DOCUMENT TEXT ---\n{text}"
        
        # Call Claude
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=800,
            messages=[{
                "role": "user",
                "content": full_prompt
            }]
        )
        
        summary = response.content[0].text
        
        logger.info(f"Document processed: {document_type}, {len(text)} chars extracted")
        
        return {
            "summary": summary,
            "document_type": document_type,
            "text_length": len(text),
            "pages_extracted": text.count("--- Page"),
            "error": None
        }
        
    except ImportError:
        return {"error": "pypdf not installed. Run: pip install pypdf"}
    except Exception as e:
        logger.error(f"Document processing error: {e}")
        return {"error": str(e)}


def detect_document_type(text: str) -> str:
    """Detect document type from content."""
    text_lower = text.lower()[:2000]
    
    if "manifesto" in text_lower or "election programme" in text_lower:
        return "manifesto"
    elif "bill" in text_lower and ("house of representatives" in text_lower or "senate" in text_lower):
        return "bill"
    elif "budget" in text_lower or "appropriation" in text_lower:
        return "budget"
    
    return "unknown"


def process_sync(document_url: str, doc_type: str = "unknown", question: str = "") -> Dict:
    """Synchronous version for simpler use cases."""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(process_document(document_url, doc_type, question))
    finally:
        loop.close()
