"""
Localization Router for Language Management
"""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel

from app.auth.api_keys import APIKey, require_api_key, get_api_key
from app.auth.rbac import Permission, check_permission
from app.services.localization import LocalizationService, Language, LocalizedString

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/localization", tags=["localization"])


# =====================
# Pydantic Models
# =====================

class SetLanguageRequest(BaseModel):
    """Request to set user language."""
    language: str  # en, pcm, yo, ha, ig


class TranslateRequest(BaseModel):
    """Request to translate a key."""
    key: str
    language: Optional[str] = None


class AddTranslationRequest(BaseModel):
    """Request to add a translation."""
    key: str
    en: str
    pcm: Optional[str] = None
    yo: Optional[str] = None
    ha: Optional[str] = None
    ig: Optional[str] = None


# =====================
# User Endpoints
# =====================

@router.get("/languages")
async def list_languages():
    """Get list of supported languages."""
    return {
        "languages": [
            {
                "code": Language.ENGLISH.value,
                "name": "English",
                "native_name": "English"
            },
            {
                "code": Language.PIDGIN.value,
                "name": "Nigerian Pidgin",
                "native_name": "Naija Pidgin"
            },
            {
                "code": Language.YORUBA.value,
                "name": "Yoruba",
                "native_name": "Yorùbá"
            },
            {
                "code": Language.HAUSA.value,
                "name": "Hausa",
                "native_name": "Hausa"
            },
            {
                "code": Language.IGBO.value,
                "name": "Igbo",
                "native_name": "Igbo"
            }
        ]
    }


@router.get("/me/language")
async def get_my_language(
    api_key: APIKey = Depends(require_api_key)
):
    """Get current user's language preference."""
    language = LocalizationService.get_user_language(api_key.key_id)

    return {
        "language": language.value,
        "name": {
            Language.ENGLISH: "English",
            Language.PIDGIN: "Nigerian Pidgin",
            Language.YORUBA: "Yoruba",
            Language.HAUSA: "Hausa",
            Language.IGBO: "Igbo"
        }.get(language, "English")
    }


@router.post("/me/language")
async def set_my_language(
    request: SetLanguageRequest,
    api_key: APIKey = Depends(require_api_key)
):
    """Set current user's language preference."""
    try:
        language = Language(request.language)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid language code: {request.language}. "
                   f"Valid codes: en, pcm, yo, ha, ig"
        )

    LocalizationService.set_user_language(api_key.key_id, language)

    confirmation = LocalizationService.translate(
        "language_changed",
        language=language
    )

    return {
        "success": True,
        "language": language.value,
        "message": confirmation
    }


@router.post("/detect")
async def detect_language(
    text: str = Query(..., min_length=1, max_length=1000)
):
    """Detect language of given text."""
    detected = LocalizationService.detect_language(text)

    return {
        "text": text[:100] + "..." if len(text) > 100 else text,
        "detected_language": detected.value,
        "confidence": "high" if len(text) > 50 else "medium"
    }


@router.get("/translate/{key}")
async def translate_key(
    key: str,
    language: Optional[str] = None,
    api_key: Optional[APIKey] = Depends(get_api_key)
):
    """Get translation for a specific key."""
    # Determine language
    lang = None
    if language:
        try:
            lang = Language(language)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid language code: {language}"
            )
    elif api_key:
        lang = LocalizationService.get_user_language(api_key.key_id)

    translation = LocalizationService.translate(
        key,
        language=lang
    )

    if translation == key:
        raise HTTPException(
            status_code=404,
            detail=f"Translation key not found: {key}"
        )

    return {
        "key": key,
        "language": lang.value if lang else "en",
        "text": translation
    }


@router.get("/menu")
async def get_localized_menu(
    language: Optional[str] = None,
    api_key: Optional[APIKey] = Depends(get_api_key)
):
    """Get main menu in specified or user's language."""
    lang = None
    if language:
        try:
            lang = Language(language)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid language code: {language}"
            )
    elif api_key:
        lang = LocalizationService.get_user_language(api_key.key_id)

    menu_text = LocalizationService.get_menu(language=lang)

    return {
        "language": lang.value if lang else "en",
        "menu": menu_text
    }


@router.get("/language-selection")
async def get_language_selection():
    """Get language selection menu for users."""
    return {
        "menu": LocalizationService.get_language_selection_menu()
    }


# =====================
# Admin Endpoints
# =====================

@router.get("/admin/translations")
async def list_all_translations(
    api_key: APIKey = Depends(require_api_key)
):
    """List all translation keys and their translations. Requires admin."""
    if not check_permission(api_key.role, Permission.SYSTEM_CONFIG):
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    return LocalizationService.get_all_translations()


@router.post("/admin/translations")
async def add_translation(
    request: AddTranslationRequest,
    api_key: APIKey = Depends(require_api_key)
):
    """Add or update a translation. Requires admin."""
    if not check_permission(api_key.role, Permission.SYSTEM_CONFIG):
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    localized = LocalizedString(
        key=request.key,
        en=request.en,
        pcm=request.pcm,
        yo=request.yo,
        ha=request.ha,
        ig=request.ig
    )

    LocalizationService.add_translation(localized)

    return {
        "success": True,
        "key": request.key,
        "message": "Translation added/updated"
    }


@router.get("/admin/user-languages")
async def get_user_language_stats(
    api_key: APIKey = Depends(require_api_key)
):
    """Get statistics on user language preferences. Requires admin."""
    if not check_permission(api_key.role, Permission.ANALYTICS_READ):
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    language_counts = {}
    for lang in LocalizationService._user_languages.values():
        lang_code = lang.value
        language_counts[lang_code] = language_counts.get(lang_code, 0) + 1

    total_users = len(LocalizationService._user_languages)

    return {
        "total_users_with_preference": total_users,
        "by_language": language_counts,
        "default_language": Language.ENGLISH.value
    }


# =====================
# WhatsApp Integration Helper
# =====================

@router.post("/whatsapp/process-language-selection")
async def process_whatsapp_language_selection(
    user_id: str = Query(..., description="WhatsApp user identifier"),
    selection: str = Query(..., description="User's selection (1-5 or language name)")
):
    """
    Process language selection from WhatsApp user.
    Used by the WhatsApp message handler.
    """
    language = LocalizationService.parse_language_selection(selection)

    if not language:
        return {
            "success": False,
            "message": "Invalid selection. Please choose 1-5.",
            "show_menu": True
        }

    LocalizationService.set_user_language(user_id, language)

    # Get confirmation in new language
    confirmation = LocalizationService.translate(
        "language_changed",
        language=language
    )

    # Get menu in new language
    menu = LocalizationService.get_menu(language=language)

    return {
        "success": True,
        "language": language.value,
        "confirmation": confirmation,
        "menu": menu
    }
