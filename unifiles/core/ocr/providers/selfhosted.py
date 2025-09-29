from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import httpx
from loguru import logger

from ..base import BaseOCRProvider
from ..config.selfhosted import SelfHostedConfig


class SelfHostedOCRProvider(BaseOCRProvider):
    """Minimal, synchronous HTTP OCR client for a self-hosted endpoint.

    Configuration (from .env):
    - `UNIFILES_SERVICE_OCR_SELFHOSTED_0_URL`    Required. Full endpoint URL (e.g. http://host:1288/infer)
    - `UNIFILES_SERVICE_OCR_SELFHOSTED_0_PROMPT` Required. Included in every request

    Request contract:
    - Method: POST `<URL from env>`
    - JSON body: {"image_path": "<local path or URL>", "prompt": "<required>"}

    Response handling:
    - Return response body as string (no JSON parsing)

    Notes:
    - No authentication, no image downloading/saving, no layout parsing
    - Synchronous only; async paths use thread wrappers from BaseOCRProvider
    """

    def __init__(self, config: Optional[SelfHostedConfig] = None):
        super().__init__(config or SelfHostedConfig())

    # --------------------
    # Public API (sync)
    # --------------------
    def process_file(self, file_path: Union[str, Path]) -> str:
        """Process local file with OCR.

        - If it's a PDF, render pages to images and OCR per page, then merge.
        - If it's an image, send directly.
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

        # Image or other single-file path: validate size, then send
        if not self.validate_file(p):
            logger.error(f"File validation failed: {p}")
            return ""

        payload = {"image_path": str(p), "prompt": self.config.get_prompt()}
        return self._post_and_read(payload)

    # TODO: 目前仅支持同步上传单个图片文件，对单个PDF文件进行OCR暂未实现、需要自部署时候在服务端实现
    def process_url(self, url: str) -> str:
        if not self.config.validate():
            return ""
        payload = {"image_path": url, "prompt": self.config.get_prompt()}
        return self._post_and_read(payload)

    # --------------------
    # Minimal HTTP call
    # --------------------
    def _post_and_read(self, payload: Dict[str, Any]) -> str:
        url = self.config.get_url()
        try:
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(
                    url, headers={"Content-Type": "application/json"}, json=payload
                )
                resp.raise_for_status()

            return resp.text or ""
        except httpx.HTTPError as e:
            logger.error(f"Self-hosted OCR request failed: {e!s}")
            return ""

    # --------------------
    # PDF -> images + per-page OCR
    # --------------------
    def _process_pdf(self, pdf_path: Path) -> str:
        """Render PDF pages to images and OCR per page. Returns combined text.

        Notes:
        - Uses pdfplumber.page.to_image() if available. If rendering fails, returns empty string.
        - Each page result is concatenated with page headers for clarity when multi-page.
        """
        texts: List[str] = []
        try:
            import pdfplumber  # Lazy import
            import warnings

            warnings.filterwarnings("ignore", category=UserWarning, module="pdfminer")

            images_dir = pdf_path.parent / f"{pdf_path.stem}_pages"
            images_dir.mkdir(parents=True, exist_ok=True)

            with pdfplumber.open(str(pdf_path)) as pdf:
                page_count = len(pdf.pages)
                for i, page in enumerate(pdf.pages):
                    try:
                        to_img = getattr(page, "to_image", None)
                        if not callable(to_img):
                            logger.error("pdfplumber page.to_image() unavailable; abort PDF OCR")
                            return ""

                        img_path = images_dir / f"page_{i+1}.png"
                        img_obj = to_img(resolution=150)
                        save = getattr(img_obj, "save", None)
                        if not callable(save):
                            logger.error("pdfplumber image object missing save(); abort PDF OCR")
                            return ""
                        save(str(img_path))

                        payload = {
                            "image_path": str(img_path),
                            "prompt": self.config.get_prompt(),
                        }
                        text = self._post_and_read(payload)
                        if text and text.strip():
                            header = f"## Page {i + 1}\n\n" if page_count > 1 else ""
                            texts.append(header + text.strip())
                    except Exception as e:
                        logger.warning(f"Failed to OCR page {i+1}: {e!s}")
                        continue
        except Exception as e:
            logger.error(f"PDF processing failed: {e!s}")
            return ""

        return "\n\n---\n\n".join(texts)

    # --------------------
    # Abstract requirements (no-op/minimal)
    # --------------------
    def _extract_data_from_response(self, response: Any) -> Tuple[str, List[Any]]:
        return "", []

    def save_to_images(
        self, images: List[Any], output_dir: Optional[Union[str, Path]] = None
    ) -> None:
        return None
