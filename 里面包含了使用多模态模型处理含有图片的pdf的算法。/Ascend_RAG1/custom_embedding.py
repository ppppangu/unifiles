import json
import time
import logging
import requests
from langchain.embeddings.base import Embeddings
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from typing import Generator
from tqdm import tqdm
from pydantic import BaseModel
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Set up logging for better debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CustomEmbeddings(Embeddings):
    def __init__(self, log_level: str = 'err', api_url: str ="http://172.20.18.231:9009/embed"):
        self.api_url = api_url
        self.log = log_level
        
        if self.log == 'err':
            logger.setLevel(logging.ERROR)
        elif self.log == 'info':
            logger.setLevel(logging.INFO)
        elif self.log == 'debug':
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.ERROR)
            logger.error(f"Invalid log level: {self.log}. Setting log level to ERROR.")

    def embed_documents(self, texts):
        embeddings = []
        with tqdm(total=len(texts), desc="Generating embeddings") as pbar:
            for text in texts:
                try:
                    embedding = self._get_embedding(text)
                    embeddings.append(embedding)
                except Exception as e:
                    logger.error(
                        f"Error generating embedding for text: {text}. Error: {e}"
                    )
                pbar.update(1)
        return embeddings

    def embed_query(self, text):
        try:
            return self._get_embedding(text)
        except Exception as e:
            logger.error(f"Error generating embedding for query: {text}. Error: {e}")
            return []

    def _get_embedding(self, text):
        try:
            logger.info(
                f"Requesting embedding for text: {text[:50]}..."
            )
            # Log the first 50 characters
            response = requests.post(self.api_url, json={"text": text})
            response.raise_for_status()  # Will raise an HTTPError for bad responses
            return response.json().get("embedding")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error connecting to embedding service: {e}")
            raise Exception(f"Error connecting to embedding service: {str(e)}")


# Add retry logic for requests
def create_session():
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


session = create_session()
