"""
Unified JSON Parsing Utilities for Decide9ja.
Single source of truth for extracting JSON from LLM responses.
Import this instead of writing custom JSON parsing.
"""
import json
import re
import logging
from typing import Any, Dict, List, Optional, TypeVar, Type
from dataclasses import dataclass

logger = logging.getLogger(__name__)

T = TypeVar('T')


class JSONParseError(Exception):
    """Raised when JSON parsing fails after all strategies."""
    pass


def extract_json(
    text: str,
    default: Optional[Dict] = None,
    strict: bool = False,
) -> Dict[str, Any]:
    """
    Extract JSON from LLM response text using multiple strategies.
    
    This is the MAIN function to use across the codebase.
    
    Args:
        text: Raw text from LLM (may contain markdown, explanation, etc.)
        default: Default dict to return if parsing fails (None raises error)
        strict: If True, raise JSONParseError on failure instead of returning default
        
    Returns:
        Parsed JSON dict
        
    Raises:
        JSONParseError: If strict=True and parsing fails
    """
    if not text:
        if strict:
            raise JSONParseError("Empty text provided")
        return default or {}
    
    text = text.strip()
    
    # Pre-process: Fix common LLM issues
    text = _fix_llm_json_quirks(text)
    
    # Strategy 1: Direct parse (fastest)
    result = _try_direct_parse(text)
    if result is not None:
        return result
    
    # Strategy 2: Extract from markdown code block
    result = _try_markdown_extraction(text)
    if result is not None:
        return result
    
    # Strategy 3: Find JSON object using balanced brace matching
    result = _try_brace_matching(text)
    if result is not None:
        return result
    
    # Strategy 4: Regex extraction
    result = _try_regex_extraction(text)
    if result is not None:
        return result
    
    # Strategy 5: Try wrapping in braces (for partial JSON from LLM)
    result = _try_wrap_in_braces(text)
    if result is not None:
        return result
    
    # All strategies failed
    if strict:
        raise JSONParseError(f"Failed to extract JSON from: {text[:100]}...")
    
    logger.warning(f"JSON extraction failed, using default: {text[:50]}...")
    return default or {}


def extract_json_list(
    text: str,
    default: Optional[List] = None,
    strict: bool = False,
) -> List[Any]:
    """
    Extract JSON array from LLM response text.
    
    Args:
        text: Raw text from LLM
        default: Default list to return if parsing fails
        strict: If True, raise JSONParseError on failure
        
    Returns:
        Parsed JSON list
    """
    if not text:
        if strict:
            raise JSONParseError("Empty text provided")
        return default or []
    
    text = text.strip()
    text = _fix_llm_json_quirks(text)
    
    # Try direct parse
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except:
        pass
    
    # Try extracting from markdown
    match = re.search(r'```(?:json)?\s*(\[[\s\S]*?\])\s*```', text)
    if match:
        try:
            return json.loads(match.group(1))
        except:
            pass
    
    # Try regex
    match = re.search(r'\[[\s\S]*?\]', text)
    if match:
        try:
            return json.loads(match.group(0))
        except:
            pass
    
    if strict:
        raise JSONParseError(f"Failed to extract JSON array from: {text[:100]}...")
    
    return default or []


def _fix_llm_json_quirks(text: str) -> str:
    """Fix common issues in LLM-generated JSON."""
    # Fix Python-style booleans and None
    text = text.replace('"True"', '"true"').replace('"False"', '"false"')
    text = re.sub(r'\bTrue\b', 'true', text)
    text = re.sub(r'\bFalse\b', 'false', text)
    text = re.sub(r'\bNone\b', 'null', text)
    
    # Fix single quotes (sometimes LLMs use Python-style)
    # Only do this outside of strings - this is tricky so be conservative
    # text = text.replace("'", '"')  # Too aggressive, can break valid strings
    
    return text


def _try_direct_parse(text: str) -> Optional[Dict]:
    """Try to parse entire text as JSON."""
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass
    return None


def _try_markdown_extraction(text: str) -> Optional[Dict]:
    """Extract JSON from markdown code block."""
    # Match ```json ... ``` or ``` ... ```
    patterns = [
        r'```json\s*\n?([\s\S]*?)\n?```',
        r'```\s*\n?([\s\S]*?)\n?```',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            content = match.group(1).strip()
            content = _fix_llm_json_quirks(content)
            try:
                result = json.loads(content)
                if isinstance(result, dict):
                    return result
            except json.JSONDecodeError:
                continue
    
    return None


def _try_brace_matching(text: str) -> Optional[Dict]:
    """Find JSON object using balanced brace matching."""
    start = text.find('{')
    if start < 0:
        return None
    
    depth = 0
    in_string = False
    escape = False
    
    for i, char in enumerate(text[start:], start):
        if escape:
            escape = False
            continue
        
        if char == '\\':
            escape = True
            continue
        
        if char == '"' and not escape:
            in_string = not in_string
            continue
        
        if not in_string:
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0:
                    # Found matching closing brace
                    json_str = text[start:i+1]
                    json_str = _fix_llm_json_quirks(json_str)
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError:
                        return None
    
    return None


def _try_regex_extraction(text: str) -> Optional[Dict]:
    """Last resort: use regex to find JSON-like object."""
    # Simple pattern for key-value objects
    match = re.search(r'\{\s*"[^"]+"\s*:', text)
    if not match:
        return None
    
    start = match.start()
    # Try to find matching end
    brace_count = 0
    for i, char in enumerate(text[start:], start):
        if char == '{':
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0:
                json_str = text[start:i+1]
                json_str = _fix_llm_json_quirks(json_str)
                try:
                    return json.loads(json_str)
                except:
                    pass
                break
    
    return None


def _try_wrap_in_braces(text: str) -> Optional[Dict]:
    """
    Try wrapping partial JSON in braces.
    Handles cases like: '"is_trackable": true, "domain": "power"'
    """
    # Check if text looks like key-value pairs without braces
    if not text.startswith('{') and '"' in text and ':' in text:
        # Try wrapping in braces
        wrapped = '{' + text.strip().rstrip(',') + '}'
        try:
            result = json.loads(wrapped)
            if isinstance(result, dict):
                return result
        except:
            pass
    
    # Try removing leading/trailing whitespace and newlines
    cleaned = text.strip()
    if cleaned.startswith('"') and ':' in cleaned:
        wrapped = '{' + cleaned.rstrip(',') + '}'
        try:
            result = json.loads(wrapped)
            if isinstance(result, dict):
                return result
        except:
            pass
    
    return None


def validate_json(
    data: Dict,
    required_fields: List[str] = None,
    defaults: Dict = None,
) -> Dict:
    """
    Validate and fill missing fields with defaults.
    
    Args:
        data: Parsed JSON dict
        required_fields: List of fields that must exist
        defaults: Default values for missing fields
        
    Returns:
        Validated dict with defaults filled in
    """
    if defaults:
        for key, value in defaults.items():
            if key not in data:
                data[key] = value
    
    if required_fields:
        missing = [f for f in required_fields if f not in data]
        if missing:
            logger.warning(f"Missing required fields: {missing}")
    
    return data


def safe_json_loads(text: str, default: Any = None) -> Any:
    """
    Simple wrapper around json.loads with error handling.
    For trusted JSON strings (not LLM output).
    """
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


def safe_json_dumps(obj: Any, indent: int = None) -> str:
    """
    Safe JSON serialization with fallback.
    """
    try:
        return json.dumps(obj, indent=indent, ensure_ascii=False, default=str)
    except (TypeError, ValueError) as e:
        logger.error(f"JSON serialization failed: {e}")
        return "{}"


# ===========================================
# EXTRACTION SCHEMAS
# ===========================================

# Common default schemas for LLM responses
ISSUE_EXTRACTION_DEFAULTS = {
    "is_trackable": False,
    "domain": "governance",
    "severity": "moderate",
    "title": "",
    "location": "Nigeria",
    "politicians": [],
    "confidence": 0.5,
}

QUERY_PLAN_DEFAULTS = {
    "is_complex": False,
    "subtasks": [],
    "response_format": "single",
}


# ===========================================
# TEST
# ===========================================

if __name__ == "__main__":
    # Test cases
    test_cases = [
        # Clean JSON
        '{"is_trackable": true, "domain": "power"}',
        # Markdown wrapped
        '```json\n{"result": true}\n```',
        # Python booleans
        '{"active": True, "count": None}',
        # With explanation
        'Here is the result:\n{"status": "ok"}\nLet me explain...',
        # Nested
        '{"user": {"name": "Test"}, "items": [1,2,3]}',
        # Broken (should return default)
        'not json at all',
    ]
    
    print("Testing JSON extraction:")
    for tc in test_cases:
        result = extract_json(tc, default={"error": True})
        print(f"  Input: {tc[:40]}...")
        print(f"  Result: {result}")
        print()
