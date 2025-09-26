import asyncio
import os
import csv
import pandas as pd
import glob
import aiofiles
from typing import List
from pathlib import Path

from dotenv import load_dotenv

# Google ADK imports
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

# 用于创建消息和文件上传
from google.genai import types
from google import genai
from pydantic import BaseModel, Field


class ClassResult(BaseModel):
    class_name: str = Field(
        description="课程名称"
    )
    score: str = Field(
        description="成绩"
    )


class ExtractResults(BaseModel):
    stu_name: str = Field(description="学生姓名")
    stu_id: str = Field(description="学号")
    teacher: str = Field(description="导师姓名")
    unit: str = Field(description="培养单位")
    major: str = Field(description="专业")
    public_needed_all_score: str = Field(
        description="公共必修课总学分"
    )
    major_needed_all_score: str = Field(
        description="专业必修课总学分"
    )
    major_elective_all_score: str = Field(
        description="专业选修课总学分"
    )
    total_score: str = Field(
        description="总学分"
    )
    class_results: List[ClassResult] | List = Field(
        description="成绩单中表格内的内容，需要对里面的成绩进行提取"
    )


# Text2SQL子智能体
text2sql_agent = Agent(
    name="智能体",
    model="gemini-2.5-pro",
    tools=[],
    instruction="""
    请提取智能体中的成绩单信息，表格内是ClassResult部分的内容，以及相关的其他信息都比较完整了,必须忠于pdf
    """,
    output_schema=ExtractResults,
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
)


def save_scores_to_csv(extract_results: ExtractResults, output_file: str = "student_scores.csv"):
    """将提取的成绩数据保存为CSV文件，课程名称作为列，成绩作为内容"""
    if not extract_results.class_results:
        print("没有找到课程成绩数据")
        return
    
    # 创建学生基本信息
    student_info = {
        "学生姓名": extract_results.stu_name,
        "学号": extract_results.stu_id,
        "导师": extract_results.teacher,
        "培养单位": extract_results.unit,
        "专业": extract_results.major,
        "公共必修课总学分": extract_results.public_needed_all_score,
        "专业必修课总学分": extract_results.major_needed_all_score,
        "专业选修课总学分": extract_results.major_elective_all_score,
        "总学分": extract_results.total_score
    }
    
    # 添加课程成绩，课程名称作为列名
    for class_result in extract_results.class_results:
        if isinstance(class_result, dict):
            student_info[class_result['class_name']] = class_result['score']
        else:
            student_info[class_result.class_name] = class_result.score
    
    # 转换为DataFrame并保存
    df = pd.DataFrame([student_info])
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"成绩数据已保存到 {output_file}")
    return df


async def process_single_pdf(pdf_file_path: str, session_service, client) -> ExtractResults:
    """处理单个PDF文件"""
    try:
        print(f"开始处理: {pdf_file_path}")
        
        import uuid
        session_i = str(uuid.uuid4())
        session_id = await session_service.create_session(
            app_name="extract", user_id="user", session_id=session_i
        )

        runner = Runner(
            app_name="extract",
            agent=text2sql_agent,
            session_service=session_service,
        )
        
        # 异步读取PDF文件并上传
        async with aiofiles.open(pdf_file_path, 'rb') as f:
            file_content = await f.read()
        uploaded_file = client.files.upload(file=pdf_file_path)
        
        user_input = "请提取以下pdf中的学生相关的成绩"
        message_content = types.Content(
            parts=[
                types.Part(text=user_input),
                types.Part(
                    file_data=types.FileData(
                        file_uri=uploaded_file.uri,
                        mime_type="application/pdf",
                    ),
                ),
            ],
            role="user",
        )

        extracted_data = None
        async for event in runner.run_async(
            user_id="user", session_id=session_id.id, new_message=message_content
        ):
            print(f"  [事件] 文件: {pdf_file_path}, 作者：{event.author}，类型：{type(event).__name__}，最终：{event.is_final_response()}")
            
            # 如果是最终响应且包含提取的数据
            if event.is_final_response() and hasattr(event, 'content') and event.content:
                print(f"  [内容类型] {type(event.content)}")
                print(f"  [内容] {event.content}")
                
                try:
                    import json
                    
                    # 检查数据是否在 parts[0].text 中
                    if hasattr(event.content, 'parts') and len(event.content.parts) > 0:
                        # 数据在 parts[0].text 中
                        json_text = event.content.parts[0].text
                        print(f"  [JSON数据] {json_text[:200]}...")  # 只显示前200个字符
                        data_dict = json.loads(json_text)
                        extracted_data = ExtractResults(**data_dict)
                    elif isinstance(event.content, str):
                        # 尝试直接解析JSON字符串
                        data_dict = json.loads(event.content)
                        extracted_data = ExtractResults(**data_dict)
                    elif isinstance(event.content, dict):
                        # 如果是字典，直接构建
                        extracted_data = ExtractResults(**event.content)
                    elif isinstance(event.content, ExtractResults):
                        # 如果已经是正确的对象
                        extracted_data = event.content
                    
                    if extracted_data:
                        print(f"成功提取数据: {pdf_file_path}")
                        return extracted_data
                    else:
                        print(f"提取的数据为空: {pdf_file_path}")
                        
                except Exception as e:
                    print(f"解析数据时出错 {pdf_file_path}: {e}")
                    print(f"原始内容类型: {type(event.content)}")
                    if hasattr(event.content, 'parts'):
                        print(f"Parts数量: {len(event.content.parts)}")
                        if len(event.content.parts) > 0:
                            print(f"第一个part内容: {event.content.parts[0].text[:500]}...")
                    import traceback
                    traceback.print_exc()
                    
    except Exception as e:
        print(f"处理文件 {pdf_file_path} 时出错: {e}")
    
    return None


async def batch_process_pdfs():
    """批量处理score目录下的所有PDF文件"""
    load_dotenv()
    
    # 查找score目录下的所有PDF文件
    score_dir = Path("score")
    if not score_dir.exists():
        print("score目录不存在")
        return
    
    pdf_files = list(score_dir.glob("*.pdf"))
    if not pdf_files:
        print("score目录下没有找到PDF文件")
        return
    
    print(f"找到 {len(pdf_files)} 个PDF文件，开始并发处理...")
    
    # 初始化共享资源
    session_service = InMemorySessionService()
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    
    # 控制并发量为10，分批处理
    semaphore = asyncio.Semaphore(70)
    
    async def process_with_semaphore(pdf_file):
        async with semaphore:
            return await process_single_pdf(str(pdf_file), session_service, client)
    
    tasks = [process_with_semaphore(pdf_file) for pdf_file in pdf_files]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 收集所有成功的结果
    all_student_data = []
    for i, result in enumerate(results):
        if isinstance(result, ExtractResults):
            all_student_data.append(result)
        elif isinstance(result, Exception):
            print(f"处理 {pdf_files[i]} 时发生异常: {result}")
        else:
            print(f"处理 {pdf_files[i]} 未返回有效数据")
    
    # 保存所有数据到CSV
    if all_student_data:
        await save_all_scores_to_csv(all_student_data)
        print(f"成功处理 {len(all_student_data)} 个学生的成绩数据")
    else:
        print("没有成功提取到任何数据")
    
    # 清理客户端连接
    try:
        if hasattr(client, 'close'):
            await client.close()
        elif hasattr(client, '_client') and hasattr(client._client, 'close'):
            await client._client.close()
    except Exception as e:
        print(f"清理客户端连接时出错: {e}")


async def save_all_scores_to_csv(all_results: List[ExtractResults], output_file: str = "all_student_scores.csv"):
    """将所有学生的成绩数据保存为一个CSV文件"""
    if not all_results:
        print("没有数据需要保存")
        return
    
    all_data = []
    
    for extract_results in all_results:
        # 创建学生基本信息
        student_info = {
            "学生姓名": extract_results.stu_name,
            "学号": extract_results.stu_id,
            "导师": extract_results.teacher,
            "培养单位": extract_results.unit,
            "专业": extract_results.major,
            "公共必修课总学分": extract_results.public_needed_all_score,
            "专业必修课总学分": extract_results.major_needed_all_score,
            "专业选修课总学分": extract_results.major_elective_all_score,
            "总学分": extract_results.total_score
        }
        
        # 添加课程成绩，课程名称作为列名
        if extract_results.class_results:
            for class_result in extract_results.class_results:
                if isinstance(class_result, dict):
                    student_info[class_result['class_name']] = class_result['score']
                else:
                    student_info[class_result.class_name] = class_result.score
        
        all_data.append(student_info)
    
    # 转换为DataFrame并异步保存
    df = pd.DataFrame(all_data)
    
    # 使用aiofiles异步写入CSV
    csv_content = df.to_csv(index=False, encoding='utf-8-sig')
    async with aiofiles.open(output_file, 'w', encoding='utf-8-sig') as f:
        await f.write(csv_content)
    
    print(f"所有学生成绩数据已保存到 {output_file}")
    return df


if __name__ == "__main__":
    import asyncio

    # 批量处理score目录下的所有PDF文件
    asyncio.run(batch_process_pdfs())
