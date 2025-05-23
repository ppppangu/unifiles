from turtle import st
import gradio as gr
from query_data import query_rag
import time
from fastapi import FastAPI
import requests
import uvicorn


app = FastAPI()

def stream_response(message, history):
    res_gen, source = query_rag(message)
    response = ''
    for chunk in res_gen:
        response += chunk.content
        yield response

    for source_ch in source:
        response += source_ch
        time.sleep(0.01)
        yield response

css = '''
        .gradio-container { max-width:850px !important; margin:20px auto !important;}
        .message { padding: 10px !important; font-size: 14px !important;}
        '''

demo = gr.ChatInterface(
    css=css,
    fn=stream_response,
    title='问答机器人',
    chatbot=gr.Chatbot(height=550, bubble_full_width=False, render_markdown=True),
    theme=gr.themes.Default(spacing_size='sm', radius_size='sm'),
    textbox=gr.Textbox(placeholder="在此输入您的问题", container=False, scale=7),
    examples=['你好，你叫什么名字？', '请描述单位登记的流程'],
    submit_btn=gr.Button('提交', variant='primary'),
    clear_btn=gr.Button('清空记录'),
    retry_btn=gr.Button('重新生成'),
    undo_btn=gr.Button('撤销答案'),
)

# gradio挂载到fastapi
app = gr.mount_gradio_app(app, demo, path="/gradio")
@app.get("/get-ip")
def get_ip():
    url = "https://baidu.com"
    response = requests.get(url)

    return response.json()


uvicorn.run(app, host="0.0.0.0", port=8000)