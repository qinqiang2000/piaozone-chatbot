import logging

import requests
from fastapi import FastAPI, Request
from langchain import FAISS
from langchain.embeddings import OpenAIEmbeddings
import os
from typing import Optional

from starlette.background import BackgroundTasks

from config import OPENAI_API_KEY, FAISS_DB_PATH, YUNZHIJIA_SEND_URL, FPY_KEYWORDS
from pydantic import BaseModel
from query_data import get_chain, get_citations, get_chat_model

os.environ['OPENAI_API_KEY'] = OPENAI_API_KEY

app = FastAPI()
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
    rds = FAISS.load_local(FAISS_DB_PATH, OpenAIEmbeddings())
    global chatbot
    retriever = rds.as_retriever()
    chatbot = get_chain(retriever)


# create a chat history buffer
chat_history = {}


def fpy_question(question):
    return any(keyword in question.upper() for keyword in FPY_KEYWORDS)


def normal_chat(question, openid):
    chain = get_chat_model(openid)
    output = chain.predict(human_input=question)
    logging.info(output)

    data = {"content": output,
            "notifyParams": [{"type": "openIds", "values": [openid]}]}
    requests.post(YUNZHIJIA_SEND_URL, json=data)


def qa(question, openid, task: BackgroundTasks):
    url = YUNZHIJIA_SEND_URL

    if not openid in chat_history:
        chat_history[openid] = []

    result = chatbot({"question": question, "chat_history": chat_history[openid]})

    citations = f"\n更多详情，请参考：{get_citations(result['source_documents'])}\n"

    if result["answer"].lower().find("sorry") >= 0:
        response = result["answer"]
        task.add_task(normal_chat, question, openid)
    else:
        response = result["answer"] + citations
        chat_history[openid].append((result["question"], result["answer"]))

    data = {"content": response,
            "notifyParams": [{"type": "openIds", "values": [openid]}]}

    logging.info(f"\n{data}")

    requests.post(url, json=data)


@app.post("/chat")
async def fpy_chat(msg: RobotMsg, task: BackgroundTasks):
    filter_str = "@发票云GPT3.5"

    if len(msg.content) < 3:
        return {"success": True, "data": {"type": 2,
                                          "content": "请输入至少3个字符，以便我能理解您的问题。"}
                }

    msg.content = msg.content.replace(filter_str, "").lstrip(" ")

    logging.info(msg)

    # 异步执行QA
    task.add_task(qa, msg.content, msg.operatorOpenid, task)

    return {
        "success": True,
        "data": {"type": 2, "content": "请稍等，正在生成答案(云之家限制，我需生成全部答案后才返回)..."}
    }


@app.post("/chat_test")
async def chat_test(msg: RobotMsg, task: BackgroundTasks):
    return await fpy_chat(msg, task)


@app.post("/chatgpt")
async def chatgpt(msg: RobotMsg, task: BackgroundTasks):
    task.add_task(normal_chat, msg.content, msg.operatorOpenid)

    return {
        "success": True,
        "data": {"type": 2, "content": "请稍等，正在生成答案(云之家限制，我需生成全部答案后才返回)..."}
    }

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=80)
