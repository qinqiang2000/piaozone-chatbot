import logging

import requests
from fastapi import FastAPI, Request
from langchain import FAISS
from langchain.chat_models import ChatOpenAI
from langchain.embeddings import OpenAIEmbeddings
import os
from typing import Optional

from starlette.background import BackgroundTasks

from config import OPENAI_API_KEY, FAISS_DB_PATH, YUNZHIJIA_SEND_URL, FPY_KEYWORDS
from pydantic import BaseModel
from query_data import get_chain, get_citations, get_chat_model
from langchain.chains import RetrievalQA
from langchain.llms import OpenAI

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
    global chatbot, retrieverQA
    retriever = rds.as_retriever()
    chatbot = get_chain(retriever)

    retrieverQA = RetrievalQA.from_chain_type(llm=ChatOpenAI(temperature=0), chain_type="stuff", retriever=retriever,
                                              return_source_documents=True)


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


# 根据文档进行聊天式回答；todo: 目前效果还不如RetrievalQA 待优化
def chat_doc(question, openid, task: BackgroundTasks):
    url = YUNZHIJIA_SEND_URL

    if not openid in chat_history:
        chat_history[openid] = []

    result = chatbot({"question": question, "chat_history": chat_history[openid]})

    citations = f"\n更多详情，请参考：{get_citations(result['source_documents'])}\n"

    if result["answer"].lower().find("sorry") >= 0 and result["answer"].lower().find("chatgpt") >= 0:
        response = result["answer"]
        task.add_task(normal_chat, question, openid)
    else:
        response = result["answer"] + citations
        chat_history[openid].append((result["question"], result["answer"]))

    data = {"content": response,
            "notifyParams": [{"type": "openIds", "values": [openid]}]}

    logging.info(f"\n{data}")

    requests.post(url, json=data)


def retrieval_qa(question, openid, task: BackgroundTasks):
    url = YUNZHIJIA_SEND_URL

    ret = retrieverQA({"query": question})

    citations = f"\n更多详情，请参考：{get_citations(ret['source_documents'])}\n"

    data = {"content": ret['result'] + citations,
            "notifyParams": [{"type": "openIds", "values": [openid]}]}
    logging.info(f"\n{data}")

    requests.post(url, json=data)


@app.post("/chat")
async def fpy_chat(msg: RobotMsg, task: BackgroundTasks):
    filter_str = "@发票云知识库"

    if len(msg.content) < 3:
        return {"success": True, "data": {"type": 2,
                                          "content": "请输入至少3个字符，以便我能理解您的问题。"}
                }

    msg.content = msg.content.replace(filter_str, "").lstrip(" ")

    logging.info(msg)

    # 异步执行QA
    task.add_task(retrieval_qa, msg.content, msg.operatorOpenid, task)

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
    task.add_task(normal_chat, msg.content, msg.operatorOpenid)

    return {
        "success": True,
        "data": {"type": 2, "content": "请稍等，正在生成答案(云之家限制，我需生成全部答案后才返回)..."}
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=80)
