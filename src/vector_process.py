from asyncpg import Connection
import boto3
from src.mineru_client import MinerUClient
from src.singleton_language_embedding import get_latest_embedding_instance

class VectorProcess:
    def __init__(self,
                 pdf: bytes,
                 user_id: str,
                 knowledge_base_id: str,
                 document_id: str,
                 document_name: str,
                 pg_connection: Connection,
                 s3_connection: boto3.client,
                 bucket_name: str,
                 mineru_client: MinerUClient
                ):
        self.pdf = pdf
        self.user_id = user_id
        self.knowledge_base_id = knowledge_base_id
        self.document_id = document_id
        self.document_name = document_name
        self.pg_connection = pg_connection
        self.s3_connection = s3_connection
        self.bucket_name = bucket_name
        self.mineru_client = mineru_client

        self.content = ""

    async def ocr(self):
        await self.mineru_client.ocr()

    async def process_images(self):...
        # 

    async def run_embedding(self):...

    async def save(self):...
    