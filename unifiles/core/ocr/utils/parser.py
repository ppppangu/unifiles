import enum

import fitz
from PIL import Image
from pydantic import BaseModel, Field

# Image processing constraints for model input
MIN_PIXELS = 4 * 224 * 224  # 200,704 pixels minimum
MAX_PIXELS = 16 * 768 * 768  # 9,437,184 pixels maximum


class SupportedPdfParseMethod(enum.Enum):
    OCR = "ocr"
    TXT = "txt"


class PageInfo(BaseModel):
    """The width and height of page"""

    w: float = Field(description="the width of page")
    h: float = Field(description="the height of page")


def to_rgb(
    image: Image.Image, background_color: tuple = (255, 255, 255)
) -> Image.Image:
    """
    Convert image to RGB, handling RGBA by applying background color.

    Args:
        image: PIL Image object (any mode)
        background_color: RGB tuple for RGBA background (default: white)

    Returns:
        RGB PIL Image object
    """
    if image.mode == "RGB":
        return image

    if image.mode == "RGBA":
        # Create white background
        bg = Image.new("RGB", image.size, background_color)
        # Paste image with alpha channel as mask
        bg.paste(image, mask=image.split()[3])
        return bg

    # Convert other modes (L, P, etc.) to RGB
    return image.convert("RGB")


def align_to_factor(image: Image.Image, factor: int = 8) -> Image.Image:
    """
    Align image dimensions to be divisible by factor.

    Crops image to nearest factor-divisible dimensions.
    Important for model input stability and token efficiency.

    Args:
        image: PIL Image object
        factor: Division factor (default: 8)

    Returns:
        Aligned PIL Image object
    """
    width, height = image.size
    new_width = (width // factor) * factor
    new_height = (height // factor) * factor

    if (
        new_width > 0
        and new_height > 0
        and (new_width != width or new_height != height)
    ):
        return image.crop((0, 0, new_width, new_height))

    return image


def smart_resize(image: Image.Image, factor: int = 8) -> Image.Image:
    """
    Intelligently resize image to fit within model input constraints.

    Ensures image pixel count is between MIN_PIXELS and MAX_PIXELS.
    Maintains aspect ratio and aligns dimensions to factor divisibility.

    Args:
        image: PIL Image object
        factor: Division factor for dimension alignment (default: 8)

    Returns:
        Resized and aligned PIL Image object
    """
    width, height = image.size
    current_pixels = width * height

    # If within range, only align
    if MIN_PIXELS <= current_pixels <= MAX_PIXELS:
        return align_to_factor(image, factor)

    # Calculate scale factor
    if current_pixels < MIN_PIXELS:
        scale = (MIN_PIXELS / current_pixels) ** 0.5
    else:  # current_pixels > MAX_PIXELS
        scale = (MAX_PIXELS / current_pixels) ** 0.5

    new_width = int(width * scale)
    new_height = int(height * scale)

    # Resize first
    resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    # Then align to factor
    return align_to_factor(resized, factor)


def fitz_doc_to_image(doc, target_dpi=200, origin_dpi=None) -> dict:
    """Convert fitz.Document to image, Then convert the image to numpy array.

    Args:
        doc (_type_): pymudoc page
        dpi (int, optional): reset the dpi of dpi. Defaults to 200.

    Returns:
        dict:  {'img': numpy array, 'width': width, 'height': height }
    """
    mat = fitz.Matrix(target_dpi / 72, target_dpi / 72)
    pm = doc.get_pixmap(matrix=mat, alpha=False)

    if pm.width > 4500 or pm.height > 4500:
        mat = fitz.Matrix(72 / 72, 72 / 72)  # use fitz default dpi
        pm = doc.get_pixmap(matrix=mat, alpha=False)

    image = Image.frombytes("RGB", (pm.width, pm.height), pm.samples)
    return image


def load_images_from_pdf(pdf_file, dpi=200, start_page_id=0, end_page_id=None) -> list:
    images = []
    with fitz.open(pdf_file) as doc:
        pdf_page_num = doc.page_count
        end_page_id = (
            end_page_id
            if end_page_id is not None and end_page_id >= 0
            else pdf_page_num - 1
        )
        if end_page_id > pdf_page_num - 1:
            print("end_page_id is out of range, use images length")
            end_page_id = pdf_page_num - 1

        for index in range(0, doc.page_count):
            if start_page_id <= index <= end_page_id:
                page = doc[index]
                img = fitz_doc_to_image(page, target_dpi=dpi)
                images.append(img)
    return images
