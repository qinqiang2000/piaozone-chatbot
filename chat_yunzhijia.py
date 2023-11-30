import re
import time
import yuque_utils
import requests
from fastapi import FastAPI, Request
from typing import Optional
from starlette.background import BackgroundTasks

from assistant import Assistant
from settings import *
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

app = FastAPI()
scheduler = AsyncIOScheduler()
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
    sessionId: Optional[str] = None


@app.on_event("startup")
async def startup_event():
    # 启动定时任务：同步语雀文档到gpt assistant
    scheduler.add_job(yuque_utils.sync_yuque_docs_2_assistant, CronTrigger(hour=2))
    scheduler.start()
    logging.info("定时任务启动")


@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown()
    logging.info("定时任务关闭")


def chat_doc(msg: RobotMsg, sessionId, task: BackgroundTasks):
    global leqi_assistant
    leqi_assistant.chat(sessionId, msg.content)

    output = "抱歉，大模型响应超时，请稍后再试"
    retry = 0
    while True:
        time.sleep(1)
        answer = leqi_assistant.get_answer(sessionId)
        if answer:
            logging.info(answer)
            output = answer.value
            break

        retry += 1
        if retry > 59:
            break

    logging.info(f"{sessionId}: {msg.operatorOpenid} --> {output} ]")
    data = {"content": output,
            "notifyParams": [{"type": "openIds", "values": [msg.operatorOpenid]}]}

    requests.post(YUNZHIJIA_NOTIFY_URL, json=data)


def add_qa(msg: RobotMsg, question, answer):
    leqi_assistant.add_faq(question, answer, msg.operatorName)
    logging.info(f"语料增加成功：{question} --> {answer}")

    data = {"content": "增加语料成功",
            "notifyParams": [{"type": "openIds", "values": [msg.operatorOpenid]}]}
    requests.post(YUNZHIJIA_NOTIFY_URL, json=data)


@app.post("/chat")
async def fpy_chat(request: Request, msg: RobotMsg, task: BackgroundTasks):
    sessionId = request.headers.get("sessionId")

    # 取msg.content第一个空格之后的消息
    msg.content = " ".join(msg.content.split()[1:])
    logging.info(f"[{sessionId}]: {msg}")

    # 增加语料：正则表达式匹配 Q[] 和 A[] 内的内容，如果匹配，则说明是增加语料的请求
    question = re.findall(r'Q\[(.*?)\]', msg.content)
    answer = re.findall(r'A\[(.*?)\]', msg.content)
    if question and answer:
        task.add_task(add_qa, msg, question[0], answer[0])
    else:
        task.add_task(chat_doc, msg, sessionId, task)

    return {
        "success": True,
        "data": {"type": 2, "content": "请稍等（云之家不能streaming push）"}
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=9999)
