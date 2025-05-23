from langchain_community.document_loaders import PyPDFDirectoryLoader, Docx2txtLoader, PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter  # 递归文本拆分器
from get_embedding_fun import get_embedding_function
from langchain.schema import Document
from langchain.vectorstores import Chroma
import pdfplumber
from optimize import split_pdf_with_essay, split_pdf_with_length, split_xlsx, caculate_len4_pdf, doc_convert2_docx, docx_convert2_pdf
from typing import List
from win32com.client import Dispatch

import argparse
import os
import shutil


DATA_PATH = "data"
CHROMA_PATH = "chroma"


def main(mode: int) -> None:
    """

    :param mode: 0为默认加载文件并切块，1为自定义加载并切块
    :return: none
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Reset the database")
    args = parser.parse_args()
    if args.reset:
        print("Clearing Database")
        clear_database()

    # doc文件 -> docx
    doc_convert2_docx(DATA_PATH)

    # docx -> pdf
    docx_convert2_pdf(DATA_PATH)

    # 创建（或者更新）数据存储
    chunks = load_documents_and_split(mode)
    add_to_chroma(chunks)


# 直接读取docx
def load_docx(file_path):
    loader = Docx2txtLoader(file_path)
    return loader.load()


# 直接读取pdf
def load_pdf(file_path):
    loader = PyPDFLoader(file_path)
    return loader.load()


# 自定义 加载和划分文档
def load_documents_and_split(mode: int) -> List[Document]:

    chunks = []
    len_list = []

    for file_name in os.listdir(DATA_PATH):
        file_path = os.path.join(DATA_PATH, file_name)
        print("----------------------------file_path----------------------:", file_path)
        # 默认切分
        if mode == 0:
            if file_path.endswith(".pdf"):
                document = load_pdf(file_path)
                chunk = split_document(document)
                chunks = chunks + chunk
            # elif file_path.endswith(".docx"):
            #     document = load_docx(file_path)
            #     chunk = split_document(document)
            #     chunks = chunks + chunk
            else:
                continue
        # 自定义切分
        elif mode == 1:
            if file_path.endswith(".pdf") or file_path.endswith(".PDF"):

                length = caculate_len4_pdf(file_path)
                dic = {"name": file_name,
                       "len": length}
                len_list.append(dic)
                if length > 1024:
                    chunk = split_pdf_with_length(file_path)
                else:
                    chunk = split_pdf_with_essay(file_path)
            elif file_path.endswith("xlsx"):
                chunk = split_xlsx(file_path)
            else:
                continue
            chunks = chunks + chunk
    for index, d in enumerate(len_list, start=1):
        print(f"文件序号:{index}  -- 文件名: {d['name']} --  平均长度：{d['len']}")
    return chunks

    # document_loader = PyPDFDirectoryLoader(DATA_PATH)
    # return document_loader.load()


def split_document(documents: list[Document]):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1024,
        chunk_overlap=300,
        length_function=len,
        is_separator_regex=False,
    )

    return text_splitter.split_documents(documents)


def add_to_chroma(chunks: list[Document]):
    db = Chroma(
        persist_directory=CHROMA_PATH, embedding_function=get_embedding_function()
    )

    # 计算页面IDs
    chunks_with_ids = caculate_chunk_ids(chunks)

    # 添加或更新文档
    # 遍历数据库中的所有项，并获取所有的ID（如果是第一次运行这个程序，这个集合应该是空的）
    existing_items = db.get(include=[])
    existing_ids = set(existing_items["ids"])
    print(f"Number of existing documents in DB: {len(existing_ids)}")

    # 将那些不在数据库中的文档添加到数据库中
    new_chunks = []
    for chunk in chunks_with_ids:
        # 如果在集合中找不到ID，意味着这是一个新的块，应该进行添加
        if chunk.metadata["id"] not in existing_ids:
            new_chunks.append(chunk)

    if len(new_chunks):
        print(f"添加新文档到数据库：{len(new_chunks)}")
        new_chunk_ids = [chunk.metadata["id"] for chunk in new_chunks]
        db.add_documents(new_chunks, ids=new_chunk_ids)
        db.persist()
    else:
        print("没有新文档可以添加到数据库")


def caculate_chunk_ids(chunks):
    # 这将创建IDs，类似于 "data/monopoly.pdf:6:2"
    # Page Source : Page Number : Chunk Index

    last_page_id = None
    current_chunk_index = 0

    for chunk in chunks:
        source = chunk.metadata.get("source")
        page = chunk.metadata.get("page")
        current_page_id = f"{source}:{page}"

        # 如果当前页面的ID与之前页面的ID相同，则应该添加索引值
        if current_page_id == last_page_id:
            current_chunk_index += 1
        else:
            current_chunk_index = 0

        # 计算文本块的ID
        chunk_id = f"{current_page_id}:{current_chunk_index}"
        last_page_id = current_page_id

        # 将其添加到页面的元数据中
        chunk.metadata["id"] = chunk_id

    return chunks


def clear_database():
    if os.path.exists(CHROMA_PATH):
        shutil.rmtree(CHROMA_PATH)


if __name__ == "__main__":
    # documents = load_documents()
    # print(documents[0])
    # print("----------------------------------------------------------")
    # chunks = split_document(documents)
    # print(chunks[0])
    # doc_convert2_docx("E:\code\pythonProject\agent_1\Ascend_RAG1\data\军庄中心小学 论文 陈蕊.doc")
    main(1)
