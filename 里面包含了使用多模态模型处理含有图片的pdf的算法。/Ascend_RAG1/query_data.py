from langchain_chroma import Chroma
from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import LLMChainExtractor

from get_embedding_fun import get_embedding_function
from dotenv import load_dotenv
from optimize import split_pdf


load_dotenv()

CHROMA_PATH = "chroma"

PROMPT_TEMPLATE = """
你是北京昇腾公司的问答机器人。

只根据下面的内容进行问答，如果不确定答案，请告诉我你不知道:

{context}

---

根据上面的内容对问题进行中文回答: {question}
"""


# 问答
def query_rag(query_text: str, from_model: str = 'local'):
    # 加载数据库
    embedding_function = get_embedding_function()
    db = Chroma(
        persist_directory=CHROMA_PATH,
        embedding_function=embedding_function
    )

    if from_model == 'local':
        model = ChatOpenAI(
            model="qwen2.5-72b",
            api_key="none",
            base_url="http://172.20.18.231:1035/v1",
            streaming=True
        )
    else:
        raise ValueError("Invalid model name")

    # 初始化基础检索器
    base_retriever = db.as_retriever(search_kwargs={"k": 5})  # 初步检索 5 个结果

    compressor = LLMChainExtractor.from_llm(model)

    # 创建压缩检索器（包含 reranking）
    compression_retriever = ContextualCompressionRetriever(
        base_compressor=compressor,
        base_retriever=base_retriever
    )

    # 检索数据库（带 reranking）
    reranked_results = compression_retriever.get_relevant_documents(query_text)

    # 调试：打印 reranked_results
    print(f"Reranked results: {reranked_results}")

    # 构建prompt
    context_text = "\n\n---\n\n".join([doc.page_content for doc in reranked_results])
    prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    prompt = prompt_template.format(context=context_text, question=query_text)

    print(f"prompt: {prompt}")

    response_generator = model.stream(prompt)

    sources = ['> ' + doc.metadata.get("id", None) for doc in reranked_results]
    sources = '\n'.join(sources)

    formatted_source = f"\n\n\n检索答案出自以下文件: \n{sources}"


    # if from_model == 'local':
    #     model = ChatOpenAI(
    #         model="llama_65b",
    #         api_key="none",
    #         base_url="http://192.168.132.143:1025/v1",
    #         streaming=True
    #     )
    # else:
    #     raise ValueError("Invalid model name")


    # 检索数据库
    results = db.similarity_search_with_score(query_text, k=5)

    # 构建prompt
    context_text = "\n\n---\n\n".join([doc.page_content for doc, _score in results])
    prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    prompt = prompt_template.format(context=context_text, question=query_text)

    print(f"prompt: {prompt}")

    response_generator = model.stream(prompt)

    sources = ['> ' + doc.metadata.get("id", None) for doc, _score in results]
    sources = '\n'.join(sources)

    formatted_source = f"\n\n\n检索答案出自以下文件: \n{sources}"
    return response_generator, formatted_source


# 问答测试
def query_rag_test(query_text: str, from_model: str = 'local'):
    # 加载数据库
    embedding_function = get_embedding_function()
    db = Chroma(
        persist_directory=CHROMA_PATH,
        embedding_function=embedding_function
    )

    if from_model == 'local':
        model = ChatOpenAI(
            model="qwen2.5-72b",
            api_key="none",
            base_url="http://172.20.18.231:1035/v1",
            streaming=True
        )
    else:
        raise ValueError("Invalid model name")

    # 检索数据库
    results = db.similarity_search_with_score(query_text, k=5)

    # 构建prompt
    context_text = "\n\n---\n\n".join([doc.page_content for doc, _score in results])
    prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    prompt = prompt_template.format(context=context_text, question=query_text)

    print(f"prompt: {prompt}")

    response = model.invoke(prompt)
    response = response.content

    sources = ['> ' + doc.metadata.get("id", None) for doc, _score in results]
    sources = '\n'.join(sources)

    formatted_source = f"\n\n\n检索答案出自以下文件: \n{sources}"

    answer = response + formatted_source
    return answer
