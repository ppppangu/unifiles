from typing import Tuple
import pdfplumber
from PyPDF2 import PdfReader, PdfWriter
import openai
import numpy as np
from enum import Enum
import cv2
from io import BytesIO
from base64 import b64encode
import pdfplumber.page
from reportlab.pdfbase import pdfmetrics  # 注册字体
from reportlab.pdfbase.ttfonts import TTFont  # 字体类
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.pagesizes import letter  # 页面的标志尺寸(8.5*inch, 11*inch)
from reportlab.lib.styles import getSampleStyleSheet  # 文本样式
from dotenv import load_dotenv
import os

openai.api_key = os.getenv("zhipu_api_key")
openai.base_url = os.getenv("zhipu_api_base")


class ProcessMode(Enum):
    ALL = 1
    ADD_REST = 2


def create_summary_page(summary: str) -> BytesIO:
    pdfmetrics.registerFont(TTFont("SimSun", "SimSun.ttf"))
    packet = BytesIO()
    doc = SimpleDocTemplate(packet, pagesize=letter)
    styles = getSampleStyleSheet()
    styles["Normal"].fontName = "SimSun"  # 设置中文字体
    styles["Normal"].fontSize = 12  # 设置字体大小
    styles["Normal"].wordWrap = "CJK"  # 设置中文自动换行
    styles["Normal"].alignment = 0  # 设置对齐方式
    styles["Normal"].firstLineIndent = 32  # 设置首行缩进
    styles["Normal"].leading = 25  # 设置行间距
    story = [Paragraph(summary, styles["Normal"])]
    doc.build(story)
    packet.seek(0)
    return packet

def process_page_with_llm(page) -> str:
    """使用OpenAI API处理单页PDF"""
    img = page.to_image(resolution=150).original
    buffered = BytesIO()
    img.save(buffered, format="JPEG")
    encoded_image = b64encode(buffered.getvalue()).decode("utf-8")

    response = openai.chat.completions.create(
        model="glm-4v-flash",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": """
                            请对图片进行描述。
                     """,
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{encoded_image}"},
                    },
                ],
            }
        ],
    )
    description = response.choices[0].message.content
    return description


def process(input_pdf_path, output_pdf_path, mode: ProcessMode = ProcessMode.ALL) -> PdfWriter:
    # 打开输入PDF
    print('Begin processing:', input_pdf_path)
    pdf_reader = PdfReader(input_pdf_path)
    pdf_writer = PdfWriter()

    # 使用pdfplumber打开PDF
    with pdfplumber.open(input_pdf_path) as pdf:
        # 逐页处理
        for page_num in range(len(pdf.pages)):
            page = pdf.pages[page_num]
            text = page.extract_text()
            # print(text)
            # print(type(page))
            process, ele_dict = detect_elements(page)
            if process:
                if mode == ProcessMode.ADD_REST and page_num + 1 < len(pdf.pages):
                    # 检测下一页pdf的高宽与当前页是否一致
                    # 如果不一致，说明已经进行过处理，那么不再处理
                    next_page = pdf.pages[page_num + 1]
                    if next_page.width != page.width or next_page.height != page.height:
                        print('Detect next page with different size, skip processing:', page_num + 1)
                        pdf_writer.add_page(pdf_reader.pages[page_num])
                        continue
                
                print('Processing page:', page_num + 1, 'with elements:', ele_dict)
                
                # 使用大模型处理
                summary = process_page_with_llm(page)
                # print("Summary:", summary)

                # 创建summary页面
                summary_page_pdf = create_summary_page(summary)
                summary_reader = PdfReader(summary_page_pdf)
                summary_page = summary_reader.pages[0]

                # 将原页面和summary页面添加到新PDF
                pdf_writer.add_page(pdf_reader.pages[page_num])
                pdf_writer.add_page(summary_page)
            else:
                # 将处理后的页面添加到新PDF
                pdf_writer.add_page(pdf_reader.pages[page_num])

    # 保存处理后的PDF
    with open(output_pdf_path, "wb") as output_file:
        pdf_writer.write(output_file)
        print('End processing:', output_pdf_path)
        
    return pdf_writer


def detect_elements(page: pdfplumber.page.Page) -> Tuple[bool, dict]:
    """
    检测页面中的表格、图片和流程图
    :param page: pdfplumber.Page 对象
    :return: 是否包含表格、图片或流程图(布尔值)，以及各元素的检测字典
    """
    # 将页面转换为图像
    img = page.to_image(resolution=150).original
    img_np = np.array(img)

    # 检测表格（可以使用边缘检测或其他图像处理方法）
    # has_table = detect_table(img_np)
    has_table = len(page.extract_tables()) > 0

    # 检测图片（可以检查页面的图像对象）
    has_image = len(page.images) > 0

    # 检测流程图（可以使用特定的图形检测算法）
    has_diagram = detect_diagram(img_np)

    ret = has_table or has_image or has_diagram
    return ret, {"table": has_table, "image": has_image, "diagram": has_diagram}


def detect_diagram(image, threshold_3k=3, threshold_1w=1, MAX=1e6) -> bool:
    # 转换为灰度图
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
    
    """不生效
    # 边缘检测
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)

    # 查找轮廓
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # 分析形状特征
    diagram_features = 0
    for contour in contours:
        # 计算轮廓面积和周长
        area = cv2.contourArea(contour)
        perimeter = cv2.arcLength(contour, True)

        if area < 100:  # 忽略太小的区域
            continue

        # 获取轮廓的近似多边形
        approx = cv2.approxPolyDP(contour, 0.04 * perimeter, True)

        # 检查是否是规则图形（矩形、菱形、圆形等）
        if len(approx) >= 4 and len(approx) <= 8:
            diagram_features += 1

        # 检查是否存在箭头形状
        if len(approx) >= 3:  # 箭头通常有7个顶点
            diagram_features += 1

    # 如果检测到足够多的流程图特征，返回True
    return diagram_features >= 2
    """
    
    contours, hierarchy = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    cnt_3k, cnt_1w = 0, 0
    for i, contour in enumerate(contours):
        s_area = cv2.contourArea(contour)
        cnt_3k += 1 if 3000 < s_area < MAX else cnt_3k
        cnt_1w += 1 if 10000 < s_area < MAX else cnt_1w
        # 可视化轮廓
    #     if s_area > threshold_3k:
    #         cv2.drawContours(image, contours, i, (0, 0, 255), 3)  # 用红色线条绘制轮廓
    #         x, y, w, h = cv2.boundingRect(contour)
    #         cv2.putText(image, f"{s_area:.2f}", (x, y + 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
    # cv2.imshow('Contours', image)
    # cv2.waitKey(0)
    # cv2.destroyAllWindows()
    return cnt_3k > threshold_3k and cnt_1w > threshold_1w


def process_all(folder_path):
    for filename in os.listdir(folder_path):
        if filename.endswith(".pdf"):
            input_pdf_path = os.path.join(folder_path, filename)
            output_pdf_path = os.path.join(folder_path, f"{os.path.splitext(filename)[0]}-new.pdf")
            process(input_pdf_path, output_pdf_path)
    

if __name__ == "__main__":
    input_pdf = "ascend\data\第四册-劳动关系.pdf"
    output_pdf = "output.pdf"
    process(input_pdf, output_pdf, mode=ProcessMode.ADD_REST)

    # process_all("ascend\data")