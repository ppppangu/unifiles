from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter  # 递归文本拆分器
from get_embedding_fun import get_embedding_function
from langchain.schema import Document
from langchain.vectorstores import Chroma
import pdfplumber
import pandas as pd
from win32com.client import Dispatch
import argparse
import os
import shutil


# DATA_PATH = "data/AI智能语音回答-市灵活(1).pdf"
DATA_PATH = "data/就业板块智能问答.xlsx"
CHROMA_PATH = "chroma"


# pdf 根据公告分块
def split_pdf_with_essay(pdf_path, title_font_size=16):
    """
    根据文件中的居中标题进行分块
    :param pdf_path: 文件路径
    :param title_font_size: 判别标题最小字号大小
    :return: 块列表
    """
    chunks = []
    current_text = ""
    current_metadata = {
        "title": "",
        "source": pdf_path,
        "page": 1
    }
    is_announcement = False  # 是否正在处理一个公告
    is_title = False
    title = ""

    # 计数，是否检测到过标题，为0则没有符合标题条件的文本
    tag = 0


    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            words = page.extract_words(extra_attrs=["size", "fontname"])  # 提取文本块、字体大小
            if not words:
                continue

            for word in words:
                text = word['text']
                font_size = word['size']
                font_name = word['fontname'].lower()

                # 找到大标题
                if font_size >= title_font_size:
                    tag = 1
                    #上一行不是标题,这是标题第一行
                    if not is_title:
                        # 处理当前的标题对应的公告内容之前，先保存之前的公告内容
                        if current_text.strip():
                            chunks.append(Document(page_content=current_text, metadata=current_metadata))
                            # 重置文本内容
                            current_text = ""
                            # 重置metadata
                            current_metadata = {"source": pdf_path, "page": page_num, "title": ""}
                        # 设置为标题
                        is_title = True
                    title += text

                    # 如果标题跨越多行，合并标题内容
                    # if current_metadata["title"]:
                    #     current_metadata["title"] += text
                    # else:
                    #     current_metadata["title"] = text

                    current_metadata["page"] = page_num  # 更新页码
                else:
                    if is_title:
                        current_metadata["title"] = title
                        title = ""
                        is_title = False

                # 判断下级标题


                current_text += text + " "
                # elif is_announcement:
                #     # 将内容添加到当前 chunk
                #     current_text += text + " "
    if tag == 0:
        current_metadata['title'] = ""
        current_metadata['page'] = 1
        current_metadata['source'] = pdf_path
    # 添加最后一个公告
    if current_text.strip():
        chunks.append(Document(page_content=current_text, metadata=current_metadata))

    print("chunks.last_page:----------------------------------------------", chunks[-1].metadata["page"])
    # print("<<<<<<<<<<<<<<<<chunks>>>>>>>>>>>>>>>>>>>:", chunks)

    return chunks

# docx文件 长度切块
# def split_docx_with_length():
#
# docx文件 标题切块
# def split_docx_with_eassy():


# 根据长度、重叠分块
def split_pdf_with_length(pdf_path, title_font_size=16, max_chunk_length=1024, chunk_overlap=256):
    """
    按照设置的块大小和块重叠进行分块
    :param pdf_path: 文件路径
    :param title_font_size: 判别标题的最小字号
    :param max_chunk_length: 最大块长度
    :param chunk_overlap: 块重叠长度
    :return:块列表
    """
    chunks = []
    current_text = ""
    current_metadata = {
        "title": "",
        "source": pdf_path,
        "page": 1
    }
    is_announcement = False  # 是否正在处理一个公告
    is_title = False
    title = ""
    last_page = 0


    with pdfplumber.open(pdf_path) as pdf:
        last_page = len(pdf.pages)
        for page_num, page in enumerate(pdf.pages, start=1):
            words = page.extract_words(extra_attrs=["size", "fontname"])  # 提取文本块、字体大小
            if not words:
                continue

            for word in words:
                text = word['text']
                font_size = word['size']
                font_name = word['fontname'].lower()

                # 找到公告标题
                if font_size >= title_font_size:
                    tag = 1
                    # 上一行不是标题,这是标题第一行
                    if not is_title:
                        # 处理当前的标题对应的公告内容之前，先保存之前的公告内容
                        if current_text.strip():
                            chunks.append(Document(page_content=current_text, metadata=current_metadata))
                            # 重置标题内容
                            title = ""
                            # 重置文本内容
                            current_text = ""
                            # 重置metadata
                            current_metadata = {"source": pdf_path, "page": page_num, "title": ""}
                        # 设置为标题
                        is_title = True
                    title += text

                    current_metadata["page"] = page_num  # 更新页码
                else:
                    if is_title:
                        current_metadata["title"] = title

                        # title = ""
                        is_title = False

                current_text += text + " "

                # 检查当前文本长度是否超过最大字数限制
                if len(current_text) >= max_chunk_length:
                    # 截取重叠部分
                    overlap_text = current_text[-chunk_overlap:]
                    current_metadata["page"] = page_num
                    # 保存当前内容为一个chunk
                    chunks.append(Document(page_content=current_text, metadata=current_metadata))
                    # 重置文本内容，保留重叠部分
                    current_text = current_metadata["title"] + " " + overlap_text + " "
                    # # 重置metadata中的标题，避免重复
                    # current_metadata["title"] = ""

    current_metadata["page"] = last_page
    # 添加最后一个公告
    if current_text.strip():
        chunks.append(Document(page_content=current_text, metadata=current_metadata))

    print("chunks.last_page:----------------------------------------------", chunks[-1].metadata["page"])
    # print("<<<<<<<<<<<<<<<<chunks>>>>>>>>>>>>>>>>>>>:", chunks)

    return chunks


# xlsx 根据问答对分块
def split_xlsx(file_path):
    """
    根据xlsx文件中每行的问答对进行分块
    :param file_path:文件路径
    :return: None
    """
    current_metadata = {
        "title": "",
        "source": file_path,
        "page": 1
    }
    # 使用 pandas 读取 Excel 文件
    df = pd.read_excel(file_path)

    # 存储问题和回答
    chunks = []

    # 按行遍历数据
    for index, row in df.iterrows():
        if index == 0 or index==1:
            continue
        if len(row.values)==3 and not pd.isna(row.values[2]):
            question = row.values[1]
            answer = row.values[2]
            current_text = "问题：" + str(question) + "\n" + "解答： " + str(answer)
            chunks.append(Document(page_content=current_text, metadata=current_metadata))

    return chunks


def caculate_len4_pdf(pdf_path, title_font_size=16, max_len=1024) -> int:
    """
    计算文件中每个居中大标题对应文本的平均长度
    :param pdf_path: 文件路径
    :param title_font_size: 判别标题的最小字号
    :param max_len: 最大平均长度
    :return:文件中每个居中大标题所对应文本的平均长度
    """
    tmp_len = 0
    count = 0
    is_title = False


    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            words = page.extract_words(extra_attrs=["size", "fontname"])  # 提取文本块、字体大小
            if not words:
                continue

            for word in words:
                text = word['text']
                font_size = word['size']
                font_name = word['fontname'].lower()

                # 找到公告标题
                if font_size >= title_font_size:
                    # 上一行不是标题,这是标题第一行
                    if not is_title:
                        # 设置为标题
                        is_title = True
                else:
                    # 标题结束
                    if is_title:
                        is_title = False
                        # 文本块计数
                        count += 1
                    # 非标题部分
                    else:
                        # 长度计数
                        tmp_len += len(text)

    if count == 0:
        count = 1

    # 平均长度
    aver_len = tmp_len / count

    return aver_len


# .doc -> .docx转换
def doc_convert2_docx(file_dir_path):
    """
    将.doc文件 转换为 .docx文件
    :param file_dir_path: doc文件路径
    :return:None
    """

    # 初始化word应用
    word = Dispatch("Word.Application")
    word.visible = False
    proj_path = os.getcwd()

    try:
        for file_name in os.listdir(file_dir_path):
            file_path = os.path.join(file_dir_path, file_name)
            if file_path.endswith(".doc"):
                if not os.path.exists(file_path.replace(".doc", ".docx")):
                    # 打开文件
                    print(f"开始转换文件：{file_name}")
                    doc_file_path = os.path.join(proj_path, file_path)
                    print(f"文件路径为：{doc_file_path}")
                    doc = word.Documents.Open(doc_file_path)
                    docx_file_path = doc_file_path.replace(".doc", ".docx")

                    # 另存
                    doc.SaveAs(docx_file_path, FileFormat=16)
                    doc.Close()
    except Exception as e:
        raise ValueError(f"无法转换 .doc 文件: {e}")
    finally:
        word.Quit()
        print("Word应用程序已关闭")


def docx_convert2_pdf(file_dir_path):
    """
    docx文件转换为pdf文件
    :param file_dir_path: doc文件路径
    :return:
    """
    # 初始化Word应用
    word = Dispatch("Word.Application")
    word.Visible = False  # 设置为不可见模式
    proj_path = os.getcwd()

    try:
        for file_name in os.listdir(file_dir_path):
            file_path = os.path.join(file_dir_path, file_name)
            if file_path.endswith(".docx"):
                if not os.path.exists(file_path.replace(".docx", ".pdf")):
                    # 打开文件
                    print(f"开始转换文件：{file_name}")
                    docx_file_path = os.path.join(proj_path, file_path)
                    print(f"文件路径为：{docx_file_path}")
                    docx = word.Documents.Open(docx_file_path)
                    pdf_file_path = docx_file_path.replace(".docx", ".pdf")

                    # 另存
                    docx.SaveAs(pdf_file_path, FileFormat=17)
                    docx.Close()
    except Exception as e:
        raise ValueError(f"无法转换 .doc 文件: {e}")
    finally:
        word.Quit()
        print("Word应用程序已关闭")


if __name__ == "__main__":
    # chunks = split_pdf(DATA_PATH)
    chunks = split_xlsx(DATA_PATH)
    # 打印结果
    for i, chunk in enumerate(chunks):
        print(f"Chunk {i + 1}:")
        print(f"Metadata: {chunk.metadata}")
        print(f"Content: {chunk.page_content[:100]}...")  # 打印前 100 个字符
        print("-" * 50)