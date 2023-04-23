import logging

import requests
from fastapi import FastAPI, Request
from langchain import FAISS
from langchain.embeddings import OpenAIEmbeddings
import os
from typing import Optional

from starlette.background import BackgroundTasks

from config import OPENAI_API_KEY, FAISS_DB_PATH, YUNZHIJIA_SEND_URL
from pydantic import BaseModel
from query_data import get_chain, get_citations

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


def qa(question, openid):
    print(question, openid)

    url = YUNZHIJIA_SEND_URL

    if not openid in chat_history:
        chat_history[openid] = []

    result = chatbot({"question": question, "chat_history": chat_history[openid]})

    chat_history[openid].append((result["question"], result["answer"]))

    citations = f"\n更多详情，请参考：{get_citations(result['source_documents'])}\n"
    if result["answer"].find("未找到") >= 0 and result["answer"].rfind("售后") > 0:
        response = result["answer"] + citations
    else:
        response = result["answer"] + citations

    data = {
        "content": response,
        "notifyParams": [
            {
                "type": "openIds",
                "values": [
                    openid
                ]
            }
        ]
    }
    print(f"openid={openid}, {data}")

    requests.post(url, json=data)


@app.post("/chat")
async def chat(msg: RobotMsg, task: BackgroundTasks):
    filter_str = "@发票云GPT3.5"

    if len(msg.content) < 3:
        return {"success": True, "data": {"type": 2,
                                          "content": "请输入至少3个字符，以便我能理解您的问题。"}
                }

    msg.content.replace(filter_str, "")
    
    print(msg)

    # 异步执行QA问问
    task.add_task(qa, msg.content, msg.operatorOpenid)

    return {
        "success": True,
        "data": {
            "type": 2,
            "content": "请稍等，正在生成答案(云之家限制，我需生成全部答案后才返回)..."
        }
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=80)
