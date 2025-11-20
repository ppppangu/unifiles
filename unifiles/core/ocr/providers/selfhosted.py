import asyncio
import base64
import json
import re
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from loguru import logger
from openai import AsyncOpenAI, OpenAI

from ..base import BaseOCRProvider
from ..config.selfhosted import SelfHostedConfig
from ..utils.parser import load_images_from_pdf, to_rgb


class SelfHostedOCRProvider(BaseOCRProvider):
    """Self-hosted, OpenAI-compatible vision OCR provider for PDFs.

    This provider only supports PDF inputs and exposes both synchronous and
    asynchronous APIs. It is designed for self-hosted OpenAI-compatible
    backends such as Qwen3-VL-8B and provides:

    - Concurrent page-level processing with configurable concurrency
    - Automatic retry with exponential backoff on transient failures
    - In-memory image handling (no temporary files on disk)
    - Optional progress callbacks for long-running async jobs
    """

    def __init__(self, config: Optional[SelfHostedConfig] = None):
        super().__init__(config or SelfHostedConfig())
        # OpenAI-compatible clients for sync and async calls
        base_url = self._normalize_base_url(self.config.get_url())
        api_key = self.config.get_api_key() or "no-key"
        self._sync_client = OpenAI(api_key=api_key, base_url=base_url)
        self._async_client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    def get_provider_name(self) -> str:
        return "selfhosted"

    def _process_image_for_model(self, image, factor: int = 8) -> Optional[str]:
        """Encode an image as base64 PNG suitable for the vision model.

        Args:
            image: PIL Image instance or path to an image file.
            factor: Reserved parameter for potential size alignment (unused).

        Returns:
            Base64-encoded PNG string if encoding succeeds, otherwise ``None``.
        """
        try:
            import io

            from PIL import Image as PILImage

            # Load the image from disk if a path is provided
            if isinstance(image, (str, Path)):
                pil_image = PILImage.open(image)
            else:
                pil_image = image

            # Normalize to RGB and handle alpha channel on a white background
            pil_image = to_rgb(pil_image)

            # Encode as PNG in memory and return base64 data URL payload
            img_byte_arr = io.BytesIO()
            pil_image.save(img_byte_arr, format="PNG", optimize=False)
            base64_image = base64.b64encode(img_byte_arr.getvalue()).decode("utf-8")
            return base64_image
        except Exception as e:
            logger.error(f"Failed to process image for model: {e!s}")
            return None

    def _normalize_base_url(self, url: str) -> str:
        suffix = "/chat/completions"
        if url.endswith(suffix):
            return url[: -len(suffix)]
        return url.rstrip("/")

    def _send_request(self, messages: list) -> str:
        """Send a synchronous chat completion request and return the text content."""
        try:
            resp = self._sync_client.chat.completions.create(
                model=self.config.get_model(),
                messages=messages,
                temperature=self.config.get_temperature(),
                max_tokens=self.config.get_max_tokens(),
            )
            return resp.choices[0].message.content
        except Exception as e:
            logger.error(f"Self-hosted sync request failed: {e!s}")
            return ""

    def _get_image_description_sync(self, image) -> str:
        """
        Send a cropped image to LLM to get its description.
        
        Args:
            image: PIL Image object (cropped image/table)
            
        Returns:
            str: Description of the image from LLM, or empty string if failed
        """
        try:
            # Encode the cropped image
            base64_image = self._process_image_for_model(image)
            if not base64_image:
                logger.warning("Failed to encode image for description")
                return ""
            
            # Create a specific prompt for image description
            description_prompt = (
                "请简要描述这张图片的内容。"
                "如果是表格，请概括表格的主要信息和数据。"
                "如果是图表，请说明图表类型和展示的关键信息。"
                "如果是普通图片，请描述图片的主要内容。"
                "用中文回答，控制在100字以内。"
            )
            
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            },
                        },
                        {"type": "text", "text": description_prompt},
                    ],
                }
            ]
            
            # Send request to get description
            description = self._send_request(messages)
            return description.strip() if description else ""
            
        except Exception as e:
            logger.error(f"Failed to get image description: {e!s}")
            return ""

    def _dump_parse_failure(
        self,
        raw: str,
        context: Dict[str, Any],
    ) -> None:
        """Persist a parse failure to disk for offline inspection.

        The behavior is controlled by the configuration:
        - ``should_dump_parse_fail()``: feature flag
        - ``get_dump_dir()``: base directory for dump files
        """
        try:
            if not getattr(self.config, "should_dump_parse_fail", None):
                return
            if not self.config.should_dump_parse_fail():
                return

            dump_dir = Path(self.config.get_dump_dir())
            dump_dir.mkdir(parents=True, exist_ok=True)

            timestamp = time.strftime("%Y%m%d_%H%M%S")
            page = context.get("page_num") or context.get("page") or "unknown"
            doc = context.get("doc_path") or context.get("doc_id") or "unknown_doc"

            safe_doc = str(doc).replace("/", "_").replace("\\", "_")
            filename = f"{safe_doc}_page_{page}_{timestamp}.json"
            dump_path = dump_dir / filename

            payload: Dict[str, Any] = {
                "provider": "selfhosted",
                "context": context,
                "raw": raw,
            }

            with dump_path.open("w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)

            logger.info(
                f"[SelfHosted OCR] Dumped parse failure to {dump_path} "
                f"(doc={doc}, page={page})"
            )
        except Exception as dump_err:
            logger.error(f"Failed to dump parse failure: {dump_err!s}")

    def _process_pdf(self, pdf_path: Path) -> Tuple[str, List[Dict[str, Any]]]:
        """Render a PDF to images and OCR each page synchronously.

        Returns:
            Tuple[str, List[Dict[str, Any]]]: (markdown_text, images_info)
        """

        full_texts: List[str] = []
        all_images_info: List[Dict[str, Any]] = []

        try:
            images = load_images_from_pdf(str(pdf_path))
            for i, img in enumerate(images):
                try:
                    base64_image = self._process_image_for_model(img)
                    if not base64_image:
                        logger.warning(f"Failed to process image for page {i + 1}")
                        continue
                    messages = [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{base64_image}"
                                    },
                                },
                                {"type": "text", "text": self.config.get_prompt()},
                            ],
                        }
                    ]
                    json_markdown = self._send_request(messages)

                    # Parse the model output and extract text and in-memory crops
                    page_text, page_images = self._parse_and_extract(
                        json_markdown,
                        img,
                        i + 1,
                        doc_path=str(pdf_path),
                    )
                    full_texts.append(page_text)
                    all_images_info.extend(page_images)

                except Exception as e:
                    logger.warning(f"Failed to OCR page {i + 1}: {e!s}")
                    continue
        except Exception as e:
            logger.error(f"PDF processing failed: {e!s}")
            return "", []

        markdown_text = "".join(full_texts)
        logger.info(
            f"[SelfHosted OCR Sync] Processing completed: {len(markdown_text)} chars, "
            f"{len(all_images_info)} images (memory only, no disk I/O)"
        )
        return markdown_text, all_images_info

    # --------------------
    # Async helpers and PDF processing with concurrency
    # --------------------
    async def _send_request_async(self, messages: list) -> str:
        """Send an async chat completion request and return the text content."""
        resp = await self._async_client.chat.completions.create(
            model=self.config.get_model(),
            messages=messages,
            temperature=self.config.get_temperature(),
            max_tokens=self.config.get_max_tokens(),
        )
        try:
            return resp.choices[0].message.content or ""
        except Exception:
            logger.warning("Self-hosted async response has no content")
            return ""

    async def _get_image_description_async(self, image) -> str:
        """
        Async version: Send a cropped image to LLM to get its description.
        
        Args:
            image: PIL Image object (cropped image/table)
            
        Returns:
            str: Description of the image from LLM, or empty string if failed
        """
        try:
            # Encode the cropped image in a worker thread to avoid blocking
            base64_image = await asyncio.to_thread(self._process_image_for_model, image)
            if not base64_image:
                logger.warning("Failed to encode image for description")
                return ""
            
            # Create a specific prompt for image description
            description_prompt = (
                "请简要描述这张图片的内容。"
                "如果是表格，请概括表格的主要信息和数据。"
                "如果是图表，请说明图表类型和展示的关键信息。"
                "如果是普通图片，请描述图片的主要内容。"
                "用中文回答，控制在100字以内。"
            )
            
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            },
                        },
                        {"type": "text", "text": description_prompt},
                    ],
                }
            ]
            
            # Send async request to get description
            description = await self._send_request_async(messages)
            return description.strip() if description else ""
            
        except Exception as e:
            logger.error(f"Failed to get image description (async): {e!s}")
            return ""

    async def _send_request_with_retry(
        self, messages: list, page_num: int, doc_path: Optional[str] = None
    ) -> Tuple[int, str, Optional[Dict[str, Any]]]:
        """Send a request with retries and return parsed JSON on success.

        Retries are triggered on network/SDK errors, empty responses and JSON
        parsing failures (raised by ``_extract_json_from_markdown``). On the
        first successful attempt, the parsed JSON is returned so downstream
        consumers can avoid double-parsing the same payload.
        """
        max_retries = max(0, int(self.config.get_max_retries()))
        for attempt in range(max_retries + 1):
            try:
                text = await self._send_request_async(messages)
                # Treat empty content as a failure and trigger a retry
                if not text:
                    raise ValueError("Empty response content from self-hosted OCR")

                # Validate that the JSON block can be parsed; this will raise
                # on failure and be handled by the retry logic.
                parsed = self._extract_json_from_markdown(text.strip())

                if attempt > 0:
                    logger.info(f"Page {page_num} succeeded after {attempt} retries")
                return (page_num, text, parsed)
            except Exception as e:
                if attempt == max_retries:
                    logger.error(
                        f"Page {page_num} failed after {max_retries} retries: {e!s}"
                    )
                    # On final failure, persist the last response (if any) for debugging
                    try:
                        # text may not exist or may be empty; guard access via locals()
                        last_text = locals().get("text") or ""
                    except Exception:
                        last_text = ""
                    if last_text:
                        self._dump_parse_failure(
                            last_text,
                            {
                                "error": str(e),
                                "page_num": page_num,
                                "attempt": attempt,
                                "doc_path": doc_path,
                                "phase": "retry_exhausted",
                            },
                        )
                    return (page_num, "", None)
                wait_time = 2**attempt
                logger.warning(
                    f"Page {page_num} attempt {attempt + 1} failed, retrying in {wait_time}s: {e!s}"
                )
                await asyncio.sleep(wait_time)
        return (page_num, "", None)

    async def _process_single_page_async(
        self,
        page_num: int,
        img,
        semaphore: asyncio.Semaphore,
        total_pages: int,
        output_dir: Optional[Path] = None,
        progress_callback: Optional[Callable[[int, int, str, str], None]] = None,
        doc_path: Optional[str] = None,
    ) -> Tuple[int, str, List[Dict[str, Any]]]:
        """OCR a single page image under a concurrency semaphore.

        Returns:
            Tuple[int, str, List[Dict[str, Any]]]: (page_num, markdown_text, images_info)
        """
        async with semaphore:
            try:
                if progress_callback:
                    progress_callback(
                        page_num,
                        total_pages,
                        "processing",
                        f"Processing page {page_num}/{total_pages}",
                    )

                # Encode the image in a worker thread to avoid blocking the event loop
                base64_image = await asyncio.to_thread(
                    self._process_image_for_model, img
                )
                if not base64_image:
                    if progress_callback:
                        progress_callback(
                            page_num,
                            total_pages,
                            "failed",
                            f"Image encode failed for page {page_num}",
                        )
                    return (page_num, "")

                messages = [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                },
                            },
                            {"type": "text", "text": self.config.get_prompt()},
                        ],
                    }
                ]

                # Request with retries and reuse parsed JSON to avoid double parsing
                _, json_markdown, parsed_json = await self._send_request_with_retry(
                    messages, page_num, doc_path=doc_path
                )
                if not json_markdown:
                    if progress_callback:
                        progress_callback(
                            page_num,
                            total_pages,
                            "failed",
                            f"No content for page {page_num}",
                        )
                    return (page_num, "")

                # Parse and reconstruct text and image crops in a worker thread
                page_text, page_images = await asyncio.to_thread(
                    self._parse_and_extract,
                    json_markdown,
                    img,
                    page_num,
                    doc_path,
                    parsed_json,
                )

                if progress_callback:
                    progress_callback(
                        page_num,
                        total_pages,
                        "completed",
                        f"Completed page {page_num}/{total_pages}",
                    )
                return (page_num, page_text, page_images)

            except Exception as e:
                logger.error(f"Failed to process page {page_num}: {e!s}")
                if progress_callback:
                    progress_callback(
                        page_num,
                        total_pages,
                        "failed",
                        f"Error processing page {page_num}: {e!s}",
                    )
                return (page_num, "", [])

    async def _process_pdf_async(
        self,
        pdf_path: Path,
        output_dir: Optional[Path] = None,
        progress_callback: Optional[Callable[[int, int, str, str], None]] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Render a PDF to images and OCR each page concurrently.

        Returns:
            Tuple[str, List[Dict[str, Any]]]: (markdown_text, images_info)
        """
        try:
            images = load_images_from_pdf(str(pdf_path))
            if not images:
                logger.error("No pages were rendered from PDF")
                return "", []

            # Ensure an output directory exists for image consumers if needed
            if output_dir is None:
                output_dir = Path.cwd()
            output_dir.mkdir(parents=True, exist_ok=True)

            max_concurrency = max(1, int(self.config.get_max_concurrency()))
            semaphore = asyncio.Semaphore(max_concurrency)
            total_pages = len(images)
            logger.info(
                f"[SelfHosted OCR] Processing {total_pages} pages with concurrency={max_concurrency}"
            )

            tasks = [
                self._process_single_page_async(
                    i + 1,
                    img,
                    semaphore,
                    total_pages,
                    output_dir,
                    progress_callback,
                    str(pdf_path),
                )
                for i, img in enumerate(images)
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Filter out failed tasks and sort results by page number
            ordered: List[Tuple[int, str, List[Dict[str, Any]]]] = []
            for r in results:
                if isinstance(r, Exception):
                    logger.error(f"Task failed with exception: {r!s}")
                    continue
                if isinstance(r, tuple) and len(r) == 3:
                    ordered.append(r)

            ordered.sort(key=lambda x: x[0])

            # Concatenate page texts and flatten image metadata
            all_images_info: List[Dict[str, Any]] = []
            markdown_text = "".join(text for _, text, _ in ordered if text)
            for _, _, page_images in ordered:
                all_images_info.extend(page_images)

            logger.info(
                f"[SelfHosted OCR] Processing completed: {len(markdown_text)} chars, {len(all_images_info)} images"
            )
            return markdown_text, all_images_info

        except Exception as e:
            logger.error(f"Async PDF processing failed: {e!s}")
            return "", []

    def _parse_and_extract(
        self,
        json_markdown: str,
        img,
        page_num: int,
        doc_path: Optional[str] = None,
        parsed_json: Optional[Dict[str, Any]] = None,
        parse_image_content: bool = False,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Parse model output and extract page text and image crops.

        Args:
            json_markdown: Raw markdown text containing a JSON block.
            img: PIL Image for the current page.
            page_num: 1-based page index.
            doc_path: Optional document identifier used for diagnostics.
            parsed_json: Optional pre-parsed JSON; if provided, it is reused
                instead of parsing ``json_markdown`` again.
            parse_image_content: If True, include image descriptions in markdown output

        Returns:
            Tuple[str, List[Dict[str, Any]]]: (markdown_text, images_info)
            for a single page.
        """
        import io  # For in-memory PNG encoding

        out_parts: List[str] = []
        page_images_info: List[Dict[str, Any]] = []

        try:
            # Prefer the pre-parsed JSON from the caller to avoid duplicate work
            json_dict = parsed_json or self._extract_json_from_markdown(
                json_markdown.strip()
            )
            index = 0
            for el in json_dict.get("layout_elements", []):
                bbox = el["bbox"]
                abs_y1 = int(bbox[1] / 999 * img.height)
                abs_x1 = int(bbox[0] / 999 * img.width)
                abs_y2 = int(bbox[3] / 999 * img.height)
                abs_x2 = int(bbox[2] / 999 * img.width)

                category = el["category"]

                if category in ["Picture", "Table"]:
                    img_crop = img.crop((abs_x1, abs_y1, abs_x2, abs_y2))
                    # Use the semantic category as filename prefix
                    prefix = category.lower()
                    filename = f"{prefix}_{page_num}_{index}.png"

                    # Encode the crop into memory instead of writing to disk
                    img_buffer = io.BytesIO()
                    img_crop.save(img_buffer, format="PNG", optimize=False)
                    img_bytes = img_buffer.getvalue()
                    img_buffer.close()

                    # Collect image metadata and in-memory bytes for downstream consumers
                    page_images_info.append(
                        {
                            "page": page_num - 1,  # Convert to 0-indexed
                            "index": index,
                            "filename": filename,
                            "bytes": img_bytes,  # Store bytes instead of path
                            "extension": "png",
                            "size_bytes": len(img_bytes),
                        }
                    )

                    # 根据parse_image_content决定使用什么作为markdown的alt text
                    if parse_image_content:
                        # 二次调用LLM获取图像描述，并用描述替换category
                        try:
                            image_description = self._get_image_description_sync(img_crop)
                            if image_description:
                                # 使用LLM返回的描述作为alt text
                                alt_text = image_description
                            else:
                                # 如果获取描述失败，仍使用category
                                alt_text = category
                        except Exception as desc_error:
                            logger.warning(
                                f"Failed to get description for {category} on page {page_num}: {desc_error}"
                            )
                            # 失败时使用category
                            alt_text = category
                    else:
                        # 默认使用category作为alt text
                        alt_text = category
                    
                    # 生成markdown图片引用
                    out_parts.append(f"\n![{alt_text}]({filename})\n")
                    
                    index += 1
                else:
                    text = el.get("text", "")
                    out_parts.append(f"\n{text}\n")
        except Exception as e:
            logger.warning(f"Failed to parse page {page_num} result: {e!s}")
            # Persist the raw response so it can be inspected or fixed offline
            self._dump_parse_failure(
                json_markdown,
                {
                    "error": str(e),
                    "page_num": page_num,
                    "doc_path": doc_path,
                    "phase": "parse_and_extract",
                },
            )

        # Add a page separator between pages
        out_parts.append("\n\n---\n\n")

        return "".join(out_parts), page_images_info

    def _extract_json_from_markdown(self, markdown: str) -> Dict[str, Any]:
        """Extract JSON object from markdown using regex.

        Raises:
            ValueError: If no JSON block is found or JSON is invalid.
        """
        json_match = re.search(r"```json\s*(\{.*?\})\s*```", markdown, re.S)
        if not json_match:
            json_match = re.search(r"(\{.*\})", markdown, re.S)

        if not json_match:
            raise ValueError("No JSON object found in markdown response")

        try:
            return json.loads(json_match.group(1))
        except Exception as e:
            # Normalize all parse errors to ValueError so callers can retry uniformly
            raise ValueError(f"Failed to decode JSON from markdown: {e!s}") from e

    def process_url(self, url: str) -> str:
        logger.warning(
            "URL processing not supported for OpenAI-compatible format. "
            "Please download the file and use process_file() instead."
        )
        return ""

    def process_file(self, file_path: Union[str, Path]) -> str:
        """Process a local PDF file synchronously and return markdown text.

        This synchronous API returns only the combined markdown text for
        backward compatibility. To obtain image metadata, use ``aprocess_file``.
        """
        if not self.config.validate():
            return ""
        p = Path(file_path)
        if not p.exists():
            logger.error(f"File not found: {p}")
            return ""
        if p.suffix.lower() != ".pdf":
            logger.error(f"Only PDF files are supported, got: {p.suffix}")
            return ""
        # _process_pdf returns (text, images_info); this API only exposes text
        markdown_text, _ = self._process_pdf(p)
        return markdown_text

    # --------------------
    # Async public API
    # --------------------

    async def aprocess_file(
        self,
        file_path: Union[str, Path],
        output_dir: Optional[Path] = None,
        progress_callback: Optional[Callable[[int, int, str, str], None]] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Async OCR for a local PDF file with optional progress reporting.

        Args:
            file_path: Path to the PDF file to process.
            output_dir: Directory used by callers that want to persist images;
                this provider itself keeps images in memory.
            progress_callback: Optional callback for progress updates, called
                with (page_num, total_pages, status, message).

        Returns:
            Tuple[str, List[Dict[str, Any]]]: (markdown_text, images_info).
        """
        if not self.config.validate():
            return "", []

        p = Path(file_path)
        if not p.exists():
            logger.error(f"File not found: {p}")
            return "", []

        if p.suffix.lower() != ".pdf":
            logger.error(f"Only PDF files are supported, got: {p.suffix}")
            return "", []

        # Delegate to the concurrent async PDF pipeline
        return await self._process_pdf_async(p, output_dir, progress_callback)
