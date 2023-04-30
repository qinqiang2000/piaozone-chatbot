import logging

import requests
from fastapi import FastAPI, Request
from langchain import FAISS
import os
from typing import Optional
from starlette.background import BackgroundTasks
from config import OPENAI_API_KEY, YUNZHIJIA_NOTIFY_URL
from pydantic import BaseModel
from query_data import get_chain, get_citations, get_chat_model, get_embeddings

os.environ['OPENAI_API_KEY'] = OPENAI_API_KEY

app = FastAPI()
FAISS_DB_PATH = 'db'
chatbot = None


class RobotMsg(BaseModel):
    type: int
    robotId: Optional[str] = None
    robotName: Optional[str] = None
    operatorName: Optional[str] = None
    msgId: Optional[str] = None
    operatorOpenid: str = None
    content: str = None
    time: int


@app.on_event("startup")
async def startup_event():
    logging.info("loading vectorstore")
    # Load from existing index
    rds = FAISS.load_local(FAISS_DB_PATH, get_embeddings(api_type='azure'))
    retriever = rds.as_retriever()

    global chatbot
    chatbot = get_chain(retriever, api_type='azure')


# create a chat history buffer
chat_history = {}


# 直接和chatgpt聊天
def direct_chatgpt(question, openid):
    chain = get_chat_model(openid, api_type='azure')
    output = chain.predict(human_input=question)
    logging.info(output)

    data = {"content": output,
            "notifyParams": [{"type": "openIds", "values": [openid]}]}
    requests.post(YUNZHIJIA_NOTIFY_URL, json=data)


# 根据文档进行聊天式回答
def chat_doc(question, openid, task: BackgroundTasks):
    url = YUNZHIJIA_NOTIFY_URL

    if not openid in chat_history:
        chat_history[openid] = []

    result = chatbot({"question": question, "chat_history": chat_history[openid]})
    response = result["answer"]

    citations = f"\n更多详情，请参考：{get_citations(result['source_documents'])}\n"

    # 如果是不能回答的任务，则不加入chat_history，转而直接问chatgpt
    KEYWORDS = ["sorry", "chatgpt", "抱歉"]
    if any(keyword in result["answer"].lower() for keyword in KEYWORDS):
        task.add_task(direct_chatgpt, question, openid)
        pass
    else:
        response = result["answer"] + citations
        # todo: 加上history有时候会出问题,待解决
        chat_history[openid].append((result["question"], result["answer"]))

    data = {"content": response,
            "notifyParams": [{"type": "openIds", "values": [openid]}]}

    logging.info(f"\n{data}")

    requests.post(url, json=data)


@app.post("/chat")
async def fpy_chat(msg: RobotMsg, task: BackgroundTasks):
    filter_str = "@发票云知识库"

    msg.content = msg.content.replace(filter_str, "").lstrip(" ")
    logging.info(msg)

    if len(msg.content) < 3:
        return {"success": True, "data": {"type": 2, "content": "请输入至少3个字符，以便我能理解您的问题。"}}

    # 异步执行QA
    task.add_task(chat_doc, msg.content, msg.operatorOpenid, task)

    return {
        "success": True,
        "data": {"type": 2, "content": "请稍等，正在生成答案(云之家限制，我需生成全部答案后才返回)..."}
    }


@app.post("/chat_test")
async def chat_test(msg: RobotMsg, task: BackgroundTasks):
    YUNZHIJIA_SEND_URL = "https://www.yunzhijia.com/gateway/robot/webhook/send?yzjtype=0&yzjtoken=33604eb24ce34ee8a1a8577b4d992ac7"
    return await fpy_chat(msg, task)


@app.post("/chatgpt")
async def chatgpt(msg: RobotMsg, task: BackgroundTasks):
    task.add_task(direct_chatgpt, msg.content, msg.operatorOpenid)

    return {
        "success": True,
        "data": {"type": 2, "content": "请稍等，正在生成答案(云之家限制，我需生成全部答案后才返回)..."}
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=80)