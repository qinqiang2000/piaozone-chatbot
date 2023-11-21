import logging
import time

import requests
from fastapi import FastAPI, Request
from typing import Optional
from starlette.background import BackgroundTasks

from assistant import Assistant
from settings import *
from pydantic import BaseModel

app = FastAPI()
leqi_assistant = Assistant(LEQI_ASSISTANT_ID)


class RobotMsg(BaseModel):
    type: int
    robotId: Optional[str] = None
    robotName: Optional[str] = None
    operatorName: Optional[str] = None
    msgId: Optional[str] = None
    operatorOpenid: str = None
    content: str = None
    time: int


def chat_doc(msg: RobotMsg, task: BackgroundTasks):
    global leqi_assistant
    openid = msg.operatorOpenid

    leqi_assistant.chat(openid, msg.content)

    output = "抱歉，无法连接到知识库，请稍后再试"
    retry = 0
    while True:
        time.sleep(1)
        answer = leqi_assistant.get_answer(openid)
        if answer:
            break

        retry += 1
        if retry > 30:
            break

    data = {"content": output,
            "notifyParams": [{"type": "openIds", "values": [openid]}]}

    requests.post(YUNZHIJIA_NOTIFY_URL, json=data)


@app.on_event("startup")
async def startup_event():
    assistant_id = LEQI_ASSISTANT_ID
    pass


@app.post("/chat")
async def fpy_chat(msg: RobotMsg, task: BackgroundTasks):
    filter_str = "@发票云知识库"

    msg.content = msg.content.replace(filter_str, "").lstrip(" ")
    logging.info(msg)

    if len(msg.content) < 3:
        return {"success": True, "data": {"type": 2, "content": "请输入至少3个字符，以便我能理解您的问题。"}}

    # 异步执行QA
    task.add_task(chat_doc, msg, task)

    return {
        "success": True,
        "data": {"type": 2, "content": "请稍等（云之家不能streaming push）"}
    }


@app.post("/test")
async def test_chat():
    logging.info("test")
    return {
        "success": True,
        "data": {"type": 2, "content": "请稍等（云之家不能streaming push）"}
    }

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=80)
