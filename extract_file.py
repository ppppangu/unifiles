import asyncio
import os
from typing import List

from dotenv import load_dotenv

# Google ADK imports
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

# 用于创建消息
from google.genai import types
from pydantic import BaseModel, Field


class Company_final_balance(BaseModel):
    class_name: str = Field(
        description="The code of the company,The company's code in the file is generally called 'company number' or 'Registered number'.It can generally be found in the first few pages of the PDF."
    )
    score: str = Field(description="The year of the balance")
    final_balance: str = Field(
        description="The final balance of the company, only extract the final balance of the year, not the period balance"
    )


class Company_final_balances(BaseModel):
    extract_result: List[Company_final_balance] | List = Field(
        description="The extract result of the company,if not found, return empty list"
    )


# 加载环境变量
load_dotenv()


model3 = LiteLlm(
    model="gemini-2.5-pro",
    api_key=os.getenv("GEMINI_API_KEY"),
)


# Text2SQL子智能体
text2sql_agent = Agent(
    name="智能体",
    model=model3,
    tools=[],
    instruction="""
# Financial Statement Year-End Balance Extraction Prompt

## Task Description
You are a professional financial data extractor who needs to extract specified companies' annual year-end balance (Final Balance) information from uploaded financial statement PDF files.

## Specific Requirements

### 1. Document Analysis
- Carefully read and analyze the uploaded PDF financial statements
- Identify all company names mentioned in the document
- Determine the reporting period and year of the document

### 2. Processing Rules
- **Multiple Companies**: If the PDF contains information from multiple companies, extract all of them
- **Missing Data**: If a company lacks year-end balance data, explain in the "missing_data" section
- **Uncertain Data**: If data exists but is uncertain, mark it as "(to be confirmed)"
- **Unit Handling**: Use only basic currency units (yuan, pounds, etc.), prohibit using "ten thousand yuan", "thousand yuan" and similar units
- **Multiple Years**: If there are multiple years of data, extract all of them
    """,
    output_schema=Company_final_balances,
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
)


async def test():
    session_service = InMemorySessionService()

    session_id = await session_service.create_session(
        app_name="extract_final_balance", user_id="user", session_id="x"
    )

    runner = Runner(
        app_name="extract_final_balance",
        agent=text2sql_agent,
        session_service=session_service,
    )

    user_input = "请提取以下pdf的公司，年份和每年的final_balance"
    message_content = types.Content(
        parts=[
            types.Part(text=user_input),
            types.Part(
                file_data=types.FileData(
                    file_uri="https://ociyrimetvevjyusjtzm.supabase.co/storage/v1/object/public/account/00157267/00157267_MzQ0ODMxODU3NGFkaXF6a2N4.pdf",
                    mime_type="application/pdf",
                ),
            ),
        ],
        role="user",
    )

    async for event in runner.run_async(
        user_id="user", session_id=session_id.id, new_message=message_content
    ):
        print(
            f"  [事件] 作者：{event.author}，类型：{type(event).__name__}，最终：{event.is_final_response()}，内容：{event.content}"
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(test())
