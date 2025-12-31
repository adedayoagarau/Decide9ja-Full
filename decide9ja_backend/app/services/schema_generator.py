"""
Dynamic Schema Generator for Structured Data Extraction.
Generates Pydantic schemas from natural language requirements.
Based on Knowledge-Extraction-Using-Dynamic-Schema-Generation approach.
"""
import os
import json
import logging
from typing import Dict, Any, List, Optional, Type
from pydantic import BaseModel, Field, create_model
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

from anthropic import Anthropic

logger = logging.getLogger(__name__)

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


# ===========================================
# PREDEFINED SCHEMAS
# ===========================================

class NewsArticleSchema(BaseModel):
    """Schema for news articles."""
    title: str = Field(description="Article headline")
    author: Optional[str] = Field(default=None, description="Author name")
    published_date: Optional[str] = Field(default=None, description="Publication date")
    content: str = Field(description="Main article body text")
    excerpt: Optional[str] = Field(default=None, description="Article summary or lead")
    politicians_mentioned: List[str] = Field(default_factory=list, description="Politicians mentioned")
    topics: List[str] = Field(default_factory=list, description="Topics covered")
    source_url: Optional[str] = Field(default=None, description="Original URL")


class ElectionResultSchema(BaseModel):
    """Schema for election results (INEC)."""
    election_type: str = Field(description="Type of election (Presidential, Gubernatorial, etc)")
    state: Optional[str] = Field(default=None, description="State name")
    constituency: Optional[str] = Field(default=None, description="Constituency name")
    candidates: List[Dict[str, Any]] = Field(default_factory=list, description="Candidates and votes")
    total_votes: Optional[int] = Field(default=None, description="Total votes cast")
    winner: Optional[str] = Field(default=None, description="Winner name")
    date: Optional[str] = Field(default=None, description="Election date")


class BudgetDataSchema(BaseModel):
    """Schema for budget data (BudgIT)."""
    year: Optional[int] = Field(default=None, description="Budget year")
    ministry: Optional[str] = Field(default=None, description="Ministry or MDA")
    allocation: Optional[float] = Field(default=None, description="Budget allocation")
    category: Optional[str] = Field(default=None, description="Budget category")
    state: Optional[str] = Field(default=None, description="State if applicable")
    description: Optional[str] = Field(default=None, description="Description")


class PoliticianProfileSchema(BaseModel):
    """Schema for politician profiles."""
    name: str = Field(description="Full name")
    position: Optional[str] = Field(default=None, description="Current position")
    party: Optional[str] = Field(default=None, description="Political party")
    state: Optional[str] = Field(default=None, description="State represented")
    constituency: Optional[str] = Field(default=None, description="Constituency")
    bio: Optional[str] = Field(default=None, description="Biography")
    education: List[str] = Field(default_factory=list, description="Education history")
    previous_positions: List[str] = Field(default_factory=list, description="Previous positions")


# Schema registry
SCHEMA_REGISTRY = {
    "news_article": NewsArticleSchema,
    "election_result": ElectionResultSchema,
    "budget_data": BudgetDataSchema,
    "politician_profile": PoliticianProfileSchema,
}


# ===========================================
# SCHEMA GENERATOR
# ===========================================

SCHEMA_GENERATION_PROMPT = """You are a schema designer. Given a document type description, generate a JSON schema for extracting structured data.

Document Type: {doc_type}
Description: {description}
Sample Content: {sample_content}

Generate a JSON schema with fields that would be useful to extract. For each field, specify:
- name: field name (snake_case)
- type: string, int, float, bool, list[str], or dict
- required: true/false
- description: what this field contains

Respond with ONLY valid JSON:
{{
  "schema_name": "DocumentName",
  "fields": [
    {{"name": "field_name", "type": "string", "required": true, "description": "..."}}
  ]
}}"""


async def generate_schema_from_description(
    doc_type: str,
    description: str,
    sample_content: str = ""
) -> Dict[str, Any]:
    """
    Generate a Pydantic-compatible schema from natural language description.
    
    Args:
        doc_type: Type of document (e.g., "news_article", "election_data")
        description: Natural language description of what to extract
        sample_content: Optional sample of the content
        
    Returns:
        Dict with schema definition
    """
    from app.services.json_utils import extract_json
    
    try:
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",  # Cheaper model for schema gen
            max_tokens=500,
            temperature=0,
            messages=[{
                "role": "user",
                "content": SCHEMA_GENERATION_PROMPT.format(
                    doc_type=doc_type,
                    description=description,
                    sample_content=sample_content[:1000]
                )
            }]
        )
        
        schema_def = extract_json(response.content[0].text, default={})
        return schema_def
        
    except Exception as e:
        logger.error(f"Schema generation failed: {e}")
        return {}


def create_dynamic_model(schema_def: Dict[str, Any]) -> Type[BaseModel]:
    """
    Create a Pydantic model from a schema definition.
    
    Args:
        schema_def: Schema definition with fields
        
    Returns:
        Pydantic BaseModel class
    """
    fields = {}
    
    type_mapping = {
        "string": str,
        "str": str,
        "int": int,
        "float": float,
        "bool": bool,
        "list[str]": List[str],
        "list": List[str],
        "dict": Dict[str, Any],
    }
    
    for field in schema_def.get("fields", []):
        field_name = field.get("name", "unknown")
        field_type = type_mapping.get(field.get("type", "string"), str)
        required = field.get("required", False)
        description = field.get("description", "")
        
        if required:
            fields[field_name] = (field_type, Field(description=description))
        else:
            fields[field_name] = (Optional[field_type], Field(default=None, description=description))
    
    model_name = schema_def.get("schema_name", "DynamicModel")
    return create_model(model_name, **fields)


def get_schema_for_source(source_type: str) -> Type[BaseModel]:
    """
    Get the appropriate schema for a data source type.
    
    Args:
        source_type: Type of source (news, government, ngo)
        
    Returns:
        Pydantic schema class
    """
    mapping = {
        "news": NewsArticleSchema,
        "government": ElectionResultSchema,
        "ngo": BudgetDataSchema,
        "politician": PoliticianProfileSchema,
    }
    return mapping.get(source_type, NewsArticleSchema)


# ===========================================
# CONTENT EXTRACTOR
# ===========================================

EXTRACTION_PROMPT = """Extract structured data from this content according to the schema.

SCHEMA FIELDS:
{schema_fields}

CONTENT:
{content}

Extract the data and respond with ONLY valid JSON matching the schema.
If a field is not found, use null.
For lists, extract all relevant items found."""


async def extract_with_schema(
    content: str,
    schema: Type[BaseModel],
    source_url: str = None,
) -> Dict[str, Any]:
    """
    Extract structured data from content using a schema.
    
    Args:
        content: Raw content (markdown/text)
        schema: Pydantic schema to use
        source_url: Optional source URL
        
    Returns:
        Extracted data as dict
    """
    from app.services.json_utils import extract_json
    
    # Get schema fields description
    schema_fields = "\n".join([
        f"- {name}: {field.description or field.annotation}"
        for name, field in schema.model_fields.items()
    ])
    
    try:
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",  # Cheaper for extraction
            max_tokens=1000,
            temperature=0,
            messages=[{
                "role": "user",
                "content": EXTRACTION_PROMPT.format(
                    schema_fields=schema_fields,
                    content=content[:4000]
                )
            }]
        )
        
        data = extract_json(response.content[0].text, default={})
        
        # Add source URL if provided
        if source_url and "source_url" in schema.model_fields:
            data["source_url"] = source_url
        
        # Validate with Pydantic
        try:
            validated = schema(**data)
            return validated.model_dump()
        except Exception as e:
            logger.warning(f"Validation failed, returning raw: {e}")
            return data
            
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        return {}


def extract_with_schema_sync(
    content: str,
    schema: Type[BaseModel],
    source_url: str = None,
) -> Dict[str, Any]:
    """Synchronous wrapper."""
    import asyncio
    return asyncio.run(extract_with_schema(content, schema, source_url))


# ===========================================
# INTEGRATED EXTRACTOR
# ===========================================

async def crawl_and_extract(
    url: str,
    source_type: str = "news",
    custom_schema: Type[BaseModel] = None,
) -> Dict[str, Any]:
    """
    Crawl a URL and extract structured data.
    
    Args:
        url: URL to crawl
        source_type: Type of source for schema selection
        custom_schema: Optional custom schema
        
    Returns:
        Extracted structured data
    """
    from app.services.ai_crawler import crawl_url
    
    # Crawl the URL
    crawl_result = await crawl_url(url)
    
    if not crawl_result.success:
        return {"error": crawl_result.error, "url": url}
    
    # Select schema
    schema = custom_schema or get_schema_for_source(source_type)
    
    # Extract with schema
    extracted = await extract_with_schema(
        content=crawl_result.content_markdown,
        schema=schema,
        source_url=url
    )
    
    # Add crawl metadata
    extracted["_crawled_at"] = crawl_result.crawled_at
    extracted["_source_url"] = url
    
    return extracted


def crawl_and_extract_sync(
    url: str,
    source_type: str = "news",
) -> Dict[str, Any]:
    """Synchronous wrapper."""
    import asyncio
    return asyncio.run(crawl_and_extract(url, source_type))


# Test
if __name__ == "__main__":
    import asyncio
    
    async def test():
        # Test extraction with predefined schema
        result = await crawl_and_extract(
            url="https://punchng.com/wike-dismisses-allegations-of-secret-support-for-tinubu/",
            source_type="news"
        )
        print(json.dumps(result, indent=2, default=str))
    
    asyncio.run(test())
