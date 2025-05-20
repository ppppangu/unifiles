import boto3
import aiohttp
import asyncio

# 定义MinerU客户端类
class MinerUClient:
    def __init__(self,
                 mineru_url: str,
                 file_content: bytes,
                 # 不写file_path,默认补全
                 s3_connection: boto3.client = None,
                 bucket_name: str = None,
                 user_id: str = None,
                 knowledge_base_id: str = None,
                 document_id: str = None,
                 parse_method: str = None
                 ):
        self.mineru_url = mineru_url
        self.file_content = file_content
        self.s3_connection = s3_connection
        self.bucket_name = bucket_name
        self.user_id = user_id
        self.knowledge_base_id = knowledge_base_id
        self.document_id = document_id
        self.parse_method = parse_method
        self.s3_input_mode = 'true'
        # 用于指定改进版的app.py能从二进制读取，结果云写入s3

    async def health(self):
        try:
            await self._health_mineru_api()
            await self._health_s3_connection()
        except Exception as e:
            raise Exception(f"MinerU API server or is not healthy, please check MinerU API, error: {e}")

    async def _health_mineru_api(self):
        async with aiohttp.ClientSession() as session:
            health_url = f"{self.mineru_url}/health"
            async with session.get(health_url) as response:
                if response.status == 200:
                    return True
                else:
                    raise Exception(f"MinerU API is not healthy, status: {response.status}, response: {await response.text()}")

    async def _health_s3_connection(self):...

    async def ocr(self):
        from loguru import logger
        import asyncio

        # 一个文件在logs/ocr/{self.document_id}.log
        logger.add(f"logs/ocr/{self.document_id}.log")
        logger.info(f"Starting OCR process with file size: {len(self.file_content) if self.file_content else 'None'} bytes")
        logger.info(f"Using Mineru URL: {self.mineru_url}")

        # The file should be sent as a multipart form file, not as raw data in the form
        timeout = aiohttp.ClientTimeout(total=6000)  # Set a 30-second timeout
        async with aiohttp.ClientSession(timeout=timeout) as session:
            mineru_ocr_url = f"{self.mineru_url}/file_parse"

            # Prepare form data with proper file handling
            form_data = aiohttp.FormData()

            # Add the file as a proper file upload
            if self.file_content:
                form_data.add_field('file',
                                   self.file_content,
                                   filename=f"{self.document_id}.pdf",
                                   content_type='application/pdf')
                
            form_data.add_field('file_path', f"s3://{self.bucket_name}/{self.user_id}/file_service/{self.knowledge_base_id}/{self.document_id}.pdf")
            # 如果self.s3_input_mode为True，则将output_dir设置为s3://{self.bucket_name}/{self.user_id}/file_service/{self.knowledge_base_id}/{self.document_id}.pdf
            # Add other parameters as string values
            form_data.add_field('is_json_md_dump', 'true')
            form_data.add_field('output_dir',
                               f"s3://{self.bucket_name}/{self.user_id}/file_service/{self.knowledge_base_id}/{self.document_id}.pdf")
            form_data.add_field('return_info', 'true')
            form_data.add_field('return_content_list', 'true')
            form_data.add_field('return_images', 'true')
            form_data.add_field('parse_method', self.parse_method)  # Add the parse_method parameter to the form data
            form_data.add_field('s3_input_mode', self.s3_input_mode)  # Add the parse_method parameter to the form data

            logger.info("Sending OCR request to Mineru service")
            logger.info(f"Form data: {form_data}")
            try:
                async with session.post(mineru_ocr_url, data=form_data) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info("OCR request successful")
                        return result
                    else:
                        error_text = await response.text()
                        logger.error(f"OCR request failed: status={response.status}, response={error_text}")
                        raise Exception(f"OCR is not healthy, status: {response.status}, response: {error_text}")
            except asyncio.TimeoutError:
                logger.error("OCR request timed out after 30 seconds")
                raise Exception("OCR request timed out. The Mineru service may be overloaded or unavailable.")
            except Exception as e:
                logger.error(f"Exception during OCR request: {str(e)}")
                raise


