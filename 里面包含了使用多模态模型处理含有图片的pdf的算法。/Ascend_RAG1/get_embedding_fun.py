from langchain_openai import OpenAIEmbeddings
from custom_embedding import CustomEmbeddings
from dotenv import load_dotenv
load_dotenv()


def get_embedding_function():

    embeddings = CustomEmbeddings()

    return embeddings