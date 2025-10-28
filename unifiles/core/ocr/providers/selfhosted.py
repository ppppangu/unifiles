import base64
import json
from pathlib import Path
from typing import Any, List, Optional, Tuple, Union

import httpx
from loguru import logger

from ..base import BaseOCRProvider
from ..config.selfhosted import SelfHostedConfig


class SelfHostedOCRProvider(BaseOCRProvider):
    """OCR provider for self-hosted multimodal models with OpenAI-compatible API.

    Supports models deployed via vLLM or other OpenAI-compatible servers.
    Examples: Qwen3-VL, Qwen2-VL, LLaVA, etc.

    Configuration (from .env, X = instance_id):
    - UNIFILES_SERVICE_OCR_SELFHOSTED_X_URL: API endpoint (e.g., http://localhost:8012/v1/chat/completions)
    - UNIFILES_SERVICE_OCR_SELFHOSTED_X_MODEL: Model name (e.g., qwen3vl-2b)
    - UNIFILES_SERVICE_OCR_SELFHOSTED_X_PROMPT: OCR prompt text
    - UNIFILES_SERVICE_OCR_SELFHOSTED_X_TEMPERATURE: Optional, default 0.7
    - UNIFILES_SERVICE_OCR_SELFHOSTED_X_MAX_TOKENS: Optional, default 2048

    Request format: OpenAI chat completion with base64 encoded images
    Response format: Standard OpenAI response with choices[0].message.content
    """

    def __init__(self, config: Optional[SelfHostedConfig] = None):
        super().__init__(config or SelfHostedConfig())

    def _encode_image_to_base64(self, image_path: Path) -> Optional[str]:
        """Encode image file to base64 string.

        Args:
            image_path: Path to the image file

        Returns:
            Base64 encoded string or None if encoding fails
        """
        try:
            with open(image_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            logger.error(f"Failed to encode image to base64: {e!s}")
            return None

    def _build_request_payload(self, image_path: Path) -> Optional[dict]:
        """Build OpenAI-compatible chat completion request payload.

        Args:
            image_path: Path to the image file

        Returns:
            Request payload dict or None if building fails
        """
        # Encode image to base64
        base64_image = self._encode_image_to_base64(image_path)
        if not base64_image:
            return None

        # Determine image MIME type from extension
        ext = image_path.suffix.lower()
        mime_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }
        mime_type = mime_types.get(ext, "image/jpeg")

        # Build OpenAI format request (same as your test code)
        return {
            "model": self.config.get_model(),
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}"
                            },
                        },
                        {"type": "text", "text": self.config.get_prompt()},
                    ],
                }
            ],
            "temperature": self.config.get_temperature(),
            "max_tokens": self.config.get_max_tokens(),
            "stream": False,
        }

    def _send_request(self, payload: dict) -> str:
        """Send HTTP POST request and extract text from response.

        Args:
            payload: Request payload dict

        Returns:
            Extracted text content or empty string
        """
        url = self.config.get_url()
        try:
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(
                    url, headers={"Content-Type": "application/json"}, json=payload
                )
                resp.raise_for_status()

            # Parse OpenAI response
            response_data = json.loads(resp.text)
            if response_data and response_data.get("choices"):
                return response_data["choices"][0]["message"]["content"]
            logger.warning("Response has no choices")
            return ""

        except httpx.HTTPError as e:
            logger.error(f"HTTP request failed: {e!s}")
            return ""
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse response: {e!s}")
            return ""

    # --------------------
    # Public API
    # --------------------
    def process_file(self, file_path: Union[str, Path]) -> str:
        """Process local file with OCR.

        For PDFs: renders pages to images and processes each page
        For images: processes directly

        Args:
            file_path: Path to the file

        Returns:
            Extracted text in Markdown format
        """
        if not self.config.validate():
            return ""

        p = Path(file_path)
        if not p.exists():
            logger.error(f"File not found: {p}")
            return ""

        # PDF handling
        if p.suffix.lower() == ".pdf":
            return self._process_pdf(p)

        # Image handling
        if not self.validate_file(p):
            logger.error(f"File validation failed: {p}")
            return ""

        payload = self._build_request_payload(p)
        if not payload:
            logger.error(f"Failed to build request for {p}")
            return ""

        return self._send_request(payload)

    def process_url(self, url: str) -> str:
        """Process file from URL with OCR.

        Note: OpenAI-compatible API expects base64 encoded images,
        so URL processing is not supported. Download the file first
        and use process_file() instead.
        """
        logger.warning(
            "URL processing not supported for OpenAI-compatible format. "
            "Please download the file and use process_file() instead."
        )
        return ""

    # --------------------
    # PDF processing
    # --------------------
    def _process_pdf(self, pdf_path: Path) -> str:
        """Render PDF pages to images and OCR each page.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Combined text from all pages
        """
        texts: List[str] = []
        try:
            import warnings

            import pdfplumber

            warnings.filterwarnings("ignore", category=UserWarning, module="pdfminer")

            images_dir = pdf_path.parent / f"{pdf_path.stem}_pages"
            images_dir.mkdir(parents=True, exist_ok=True)

            with pdfplumber.open(str(pdf_path)) as pdf:
                page_count = len(pdf.pages)
                for i, page in enumerate(pdf.pages):
                    try:
                        # Render page to image
                        to_img = getattr(page, "to_image", None)
                        if not callable(to_img):
                            logger.error(
                                "pdfplumber page.to_image() unavailable; abort PDF OCR"
                            )
                            return ""

                        img_path = images_dir / f"page_{i + 1}.png"
                        img_obj = to_img(resolution=150)
                        save = getattr(img_obj, "save", None)
                        if not callable(save):
                            logger.error(
                                "pdfplumber image object missing save(); abort PDF OCR"
                            )
                            return ""
                        save(str(img_path))

                        # Build request and send
                        payload = self._build_request_payload(img_path)
                        if not payload:
                            logger.warning(f"Failed to build request for page {i + 1}")
                            continue

                        text = self._send_request(payload)
                        if text and text.strip():
                            header = f"## Page {i + 1}\n\n" if page_count > 1 else ""
                            texts.append(header + text.strip())

                    except Exception as e:
                        logger.warning(f"Failed to OCR page {i + 1}: {e!s}")
                        continue

        except Exception as e:
            logger.error(f"PDF processing failed: {e!s}")
            return ""

        return "\n\n---\n\n".join(texts)

    # --------------------
    # Abstract requirements (no-op)
    # --------------------
    def _extract_data_from_response(self, response: Any) -> Tuple[str, List[Any]]:
        """Not used - response parsing is handled in _send_request()"""
        return "", []

    def save_to_images(
        self, images: List[Any], output_dir: Optional[Union[str, Path]] = None
    ) -> None:
        """Not used - no images extracted from text-only responses"""
        return
