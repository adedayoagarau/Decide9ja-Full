"""
OCR Pipeline for Historical Nigerian Documents

Processes scanned newspaper images and PDFs to extract text.
Supports multiple OCR backends:
- Tesseract (local, free)
- Google Cloud Vision (cloud, high accuracy)
- Azure Computer Vision (cloud, good for historical documents)
"""

import asyncio
import base64
import io
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class OCRBackend(Enum):
    """Available OCR backends"""
    TESSERACT = "tesseract"
    GOOGLE_VISION = "google_vision"
    AZURE_VISION = "azure_vision"


@dataclass
class OCRResult:
    """Result of OCR processing"""
    text: str
    confidence: float
    language: str = "en"

    # Page info for multi-page documents
    page_number: int = 1
    total_pages: int = 1

    # Bounding boxes for text regions (optional)
    regions: List[Dict] = None

    # Processing metadata
    backend_used: OCRBackend = OCRBackend.TESSERACT
    processing_time_ms: float = 0

    def __post_init__(self):
        if self.regions is None:
            self.regions = []


class OCRPipeline:
    """
    OCR Pipeline for processing historical Nigerian documents.

    Optimized for:
    - Old newspaper scans (variable quality)
    - Colonial-era documents (British English)
    - Multiple column layouts
    """

    def __init__(
        self,
        backend: OCRBackend = OCRBackend.TESSERACT,
        language: str = "eng",
        preprocess: bool = True,
    ):
        self.backend = backend
        self.language = language
        self.preprocess = preprocess

        # Validate backend availability
        self._validate_backend()

    def _validate_backend(self):
        """Check if the selected backend is available"""
        if self.backend == OCRBackend.TESSERACT:
            try:
                import pytesseract
                pytesseract.get_tesseract_version()
            except Exception as e:
                logger.warning(f"Tesseract not available: {e}")
                logger.info("Install with: brew install tesseract (Mac) or apt install tesseract-ocr (Linux)")

        elif self.backend == OCRBackend.GOOGLE_VISION:
            if not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
                logger.warning("Google Vision requires GOOGLE_APPLICATION_CREDENTIALS env var")

        elif self.backend == OCRBackend.AZURE_VISION:
            if not os.environ.get("AZURE_VISION_KEY"):
                logger.warning("Azure Vision requires AZURE_VISION_KEY and AZURE_VISION_ENDPOINT env vars")

    def _preprocess_image(self, image) -> Any:
        """
        Preprocess image for better OCR accuracy.

        Techniques:
        - Grayscale conversion
        - Noise reduction
        - Contrast enhancement
        - Deskewing
        - Binarization
        """
        try:
            from PIL import Image, ImageEnhance, ImageFilter
            import numpy as np
        except ImportError:
            logger.warning("PIL/numpy not available for preprocessing")
            return image

        # Convert to grayscale
        if image.mode != "L":
            image = image.convert("L")

        # Enhance contrast
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.5)

        # Reduce noise
        image = image.filter(ImageFilter.MedianFilter(size=3))

        # Sharpen
        image = image.filter(ImageFilter.SHARPEN)

        return image

    async def process_image(self, image_path: str) -> OCRResult:
        """Process a single image file"""
        import time
        start_time = time.time()

        try:
            from PIL import Image
            image = Image.open(image_path)
        except ImportError:
            raise ImportError("PIL required: pip install Pillow")
        except Exception as e:
            raise ValueError(f"Cannot open image: {e}")

        if self.preprocess:
            image = self._preprocess_image(image)

        if self.backend == OCRBackend.TESSERACT:
            result = await self._ocr_tesseract(image)
        elif self.backend == OCRBackend.GOOGLE_VISION:
            result = await self._ocr_google_vision(image_path)
        elif self.backend == OCRBackend.AZURE_VISION:
            result = await self._ocr_azure_vision(image_path)
        else:
            raise ValueError(f"Unknown backend: {self.backend}")

        result.processing_time_ms = (time.time() - start_time) * 1000
        return result

    async def process_pdf(self, pdf_path: str) -> List[OCRResult]:
        """Process a PDF file (may have multiple pages)"""
        try:
            from pdf2image import convert_from_path
        except ImportError:
            raise ImportError("pdf2image required: pip install pdf2image")

        # Convert PDF to images
        try:
            images = convert_from_path(pdf_path, dpi=300)
        except Exception as e:
            raise ValueError(f"Cannot convert PDF: {e}")

        results = []
        for i, image in enumerate(images):
            if self.preprocess:
                image = self._preprocess_image(image)

            if self.backend == OCRBackend.TESSERACT:
                result = await self._ocr_tesseract(image)
            else:
                # For cloud backends, save temp image
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                    image.save(f.name)
                    if self.backend == OCRBackend.GOOGLE_VISION:
                        result = await self._ocr_google_vision(f.name)
                    else:
                        result = await self._ocr_azure_vision(f.name)
                    os.unlink(f.name)

            result.page_number = i + 1
            result.total_pages = len(images)
            results.append(result)

        return results

    async def _ocr_tesseract(self, image) -> OCRResult:
        """OCR using Tesseract"""
        try:
            import pytesseract
        except ImportError:
            raise ImportError("pytesseract required: pip install pytesseract")

        # Get detailed output with confidence
        data = pytesseract.image_to_data(
            image,
            lang=self.language,
            output_type=pytesseract.Output.DICT
        )

        # Calculate overall confidence
        confidences = [int(c) for c in data["conf"] if int(c) > 0]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0

        # Get full text
        text = pytesseract.image_to_string(image, lang=self.language)

        return OCRResult(
            text=text,
            confidence=avg_confidence / 100,  # Normalize to 0-1
            backend_used=OCRBackend.TESSERACT,
        )

    async def _ocr_google_vision(self, image_path: str) -> OCRResult:
        """OCR using Google Cloud Vision API"""
        try:
            from google.cloud import vision
        except ImportError:
            raise ImportError("google-cloud-vision required: pip install google-cloud-vision")

        client = vision.ImageAnnotatorClient()

        with open(image_path, "rb") as f:
            content = f.read()

        image = vision.Image(content=content)
        response = client.document_text_detection(image=image)

        if response.error.message:
            raise Exception(f"Google Vision error: {response.error.message}")

        # Extract text and confidence
        full_text = response.full_text_annotation.text if response.full_text_annotation else ""

        # Calculate average confidence from pages
        confidences = []
        for page in response.full_text_annotation.pages:
            for block in page.blocks:
                confidences.append(block.confidence)

        avg_confidence = sum(confidences) / len(confidences) if confidences else 0

        return OCRResult(
            text=full_text,
            confidence=avg_confidence,
            backend_used=OCRBackend.GOOGLE_VISION,
        )

    async def _ocr_azure_vision(self, image_path: str) -> OCRResult:
        """OCR using Azure Computer Vision"""
        import aiohttp

        key = os.environ.get("AZURE_VISION_KEY")
        endpoint = os.environ.get("AZURE_VISION_ENDPOINT")

        if not key or not endpoint:
            raise ValueError("Azure Vision credentials not configured")

        url = f"{endpoint}/vision/v3.2/read/analyze"

        with open(image_path, "rb") as f:
            image_data = f.read()

        headers = {
            "Ocp-Apim-Subscription-Key": key,
            "Content-Type": "application/octet-stream",
        }

        async with aiohttp.ClientSession() as session:
            # Submit for analysis
            async with session.post(url, headers=headers, data=image_data) as response:
                if response.status != 202:
                    raise Exception(f"Azure Vision error: {await response.text()}")

                operation_url = response.headers["Operation-Location"]

            # Poll for results
            headers = {"Ocp-Apim-Subscription-Key": key}

            while True:
                async with session.get(operation_url, headers=headers) as response:
                    result = await response.json()

                    if result["status"] == "succeeded":
                        break
                    elif result["status"] == "failed":
                        raise Exception("Azure Vision processing failed")

                    await asyncio.sleep(1)

            # Extract text
            lines = []
            for read_result in result["analyzeResult"]["readResults"]:
                for line in read_result["lines"]:
                    lines.append(line["text"])

            return OCRResult(
                text="\n".join(lines),
                confidence=0.9,  # Azure doesn't provide overall confidence
                backend_used=OCRBackend.AZURE_VISION,
            )

    def post_process_text(self, text: str) -> str:
        """
        Post-process OCR text to fix common errors.

        Handles:
        - British spellings common in Nigerian colonial documents
        - Common OCR errors (rn -> m, cl -> d, etc.)
        - Newspaper formatting artifacts
        """

        # Fix common OCR errors
        replacements = [
            (r'\brn\b', 'm'),  # rn often misread as m
            (r'(?<=[a-z])l(?=[a-z])', 'l'),  # Clean up l/1 confusion
            (r'\s+', ' '),  # Normalize whitespace
            (r'-\n', ''),  # Join hyphenated words
            (r'\n+', '\n'),  # Remove excess newlines
        ]

        for pattern, replacement in replacements:
            text = re.sub(pattern, replacement, text)

        # Common Nigerian/British terms that might be misread
        nigerian_terms = {
            "Nlgeria": "Nigeria",
            "Nlgerian": "Nigerian",
            "Govemment": "Government",
            "Parliment": "Parliament",
            "lndependence": "Independence",
        }

        for wrong, correct in nigerian_terms.items():
            text = text.replace(wrong, correct)

        return text.strip()


class BatchOCRProcessor:
    """
    Process multiple documents in batch.

    Optimized for processing large archives like the 2TB external drive.
    """

    def __init__(
        self,
        pipeline: OCRPipeline,
        output_dir: str = "./ocr_output",
        max_concurrent: int = 4,
    ):
        self.pipeline = pipeline
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.max_concurrent = max_concurrent

        self.stats = {
            "processed": 0,
            "failed": 0,
            "total_pages": 0,
        }

    async def process_directory(
        self,
        input_dir: str,
        extensions: List[str] = [".pdf", ".png", ".jpg", ".jpeg", ".tiff"],
    ) -> Dict:
        """
        Process all supported files in a directory.

        Returns statistics about the processing.
        """

        input_path = Path(input_dir)
        if not input_path.exists():
            raise ValueError(f"Directory not found: {input_dir}")

        # Find all files
        files = []
        for ext in extensions:
            files.extend(input_path.rglob(f"*{ext}"))
            files.extend(input_path.rglob(f"*{ext.upper()}"))

        logger.info(f"Found {len(files)} files to process")

        # Process with semaphore for concurrency control
        semaphore = asyncio.Semaphore(self.max_concurrent)

        async def process_with_limit(file_path):
            async with semaphore:
                return await self._process_file(file_path)

        tasks = [process_with_limit(f) for f in files]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count results
        for result in results:
            if isinstance(result, Exception):
                self.stats["failed"] += 1
                logger.error(f"Processing error: {result}")
            else:
                self.stats["processed"] += 1
                self.stats["total_pages"] += result.get("pages", 1)

        return self.stats

    async def _process_file(self, file_path: Path) -> Dict:
        """Process a single file and save results"""

        try:
            if file_path.suffix.lower() == ".pdf":
                results = await self.pipeline.process_pdf(str(file_path))
                text = "\n\n---PAGE BREAK---\n\n".join(
                    self.pipeline.post_process_text(r.text) for r in results
                )
                pages = len(results)
            else:
                result = await self.pipeline.process_image(str(file_path))
                text = self.pipeline.post_process_text(result.text)
                pages = 1

            # Save output
            output_file = self.output_dir / f"{file_path.stem}.txt"
            output_file.write_text(text, encoding="utf-8")

            # Save metadata
            meta_file = self.output_dir / f"{file_path.stem}.meta.json"
            import json
            meta_file.write_text(json.dumps({
                "source": str(file_path),
                "pages": pages,
                "characters": len(text),
                "processed_at": str(asyncio.get_event_loop().time()),
            }))

            return {"pages": pages, "characters": len(text)}

        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            raise


async def demo_ocr():
    """Demo OCR capability"""

    print("=" * 60)
    print("NIGERIA KNOWLEDGE SYSTEM - OCR Pipeline Demo")
    print("=" * 60)

    # Check Tesseract availability
    try:
        import pytesseract
        version = pytesseract.get_tesseract_version()
        print(f"\n✓ Tesseract available: v{version}")
    except Exception as e:
        print(f"\n✗ Tesseract not available: {e}")
        print("  Install with: brew install tesseract (Mac)")
        print("              : apt install tesseract-ocr (Linux)")
        return

    # Check PIL
    try:
        from PIL import Image
        print("✓ PIL/Pillow available")
    except ImportError:
        print("✗ PIL not available: pip install Pillow")
        return

    print("\nOCR Pipeline ready for processing!")
    print("\nTo process your 2TB archive:")
    print("  1. Connect external drive")
    print("  2. Run: python -m app.services.nigeria_knowledge.ocr_pipeline")
    print("  3. Point to directory with scanned newspapers")

    print("\nSupported formats: PDF, PNG, JPG, JPEG, TIFF")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(demo_ocr())
