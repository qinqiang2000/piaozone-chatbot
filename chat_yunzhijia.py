import re
import time
import yuque_utils
import requests
import httpcore
from fastapi import FastAPI, Request, Query
from typing import Optional
from starlette.background import BackgroundTasks

from common_utils import *
from assistant import Assistant
from settings import *
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

app = FastAPI()
scheduler = AsyncIOScheduler()


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


def chat_doc(leqi_assistant, yzj_token, msg: RobotMsg):
    has_time_out = False
    output = "抱歉，大模型响应超时，请稍后再试"
    session_id = msg.robotId + "~" + msg.operatorOpenid
    try:
        leqi_assistant.chat(session_id, msg.content)
    except httpcore.ConnectTimeout:
        has_time_out = True
    retry = 0
    if not has_time_out:
        while True:
            time.sleep(1)
            answer = leqi_assistant.get_answer(session_id)
            if answer:
                logging.info(answer)
                output = answer.value
                break

            retry += 1
            if retry > 59:
                break

    logging.info(f"{session_id}: {msg.operatorOpenid} --> {output} ]")
    data = {"content": output,
            "notifyParams": [{"type": "openIds", "values": [msg.operatorOpenid]}]}

    requests.post(YUNZHIJIA_NOTIFY_URL.format(yzj_token), json=data)


def add_qa(leqi_assistant, yzj_token, msg: RobotMsg, question, answer):
    output = "语料增加成功"
    try:
        leqi_assistant.add_faq(question, answer, msg.operatorName)
    except Exception as e:
        logging.error(e)
        output = "语料增加失败"
    logging.info(f"{output}：{question} --> {answer}")

    data = {"content": output,
            "notifyParams": [{"type": "openIds", "values": [msg.operatorOpenid]}]}
    requests.post(YUNZHIJIA_NOTIFY_URL.format(yzj_token), json=data)


@app.post("/chat")
async def fpy_chat(request: Request, msg: RobotMsg, task: BackgroundTasks, yzj_token: str = Query(...)):
    session_id = request.headers.get("sessionId")
    msg.sessionId = session_id
    if not yzj_token:
        logging.error("云之家群聊机器人链接没有配置参数yzj_token")
        return
    # 取msg.content第一个空格之后的消息
    msg.content = " ".join(msg.content.split()[1:])
    logging.info(f"[{msg.robotId + '~' + msg.operatorOpenid}]: {msg}")
    gpt_assistant_id = get_assistant_id_by_yzj_token(yzj_token)
    leqi_assistant = Assistant(gpt_assistant_id)
    if msg.content == "请同步最新文档到Assistant":
        task.add_task(lambda:
                      yuque_utils.sync_yuque_docs_2_assistant(assistant_id=gpt_assistant_id,
                                                              notify_id=msg.operatorOpenid, yzj_token=yzj_token))
    elif msg.content:
        # 增加语料：正则表达式匹配 Q[] 和 A[] 内的内容，如果匹配，则说明是增加语料的请求
        question = re.findall(r'Q\[(.*?)\]', msg.content)
        answer = re.findall(r'A\[(.*?)\]', msg.content)
        if question and answer:
            task.add_task(add_qa, leqi_assistant, yzj_token, msg, question[0], answer[0])
        else:
            task.add_task(chat_doc, leqi_assistant, yzj_token, msg)

    return {
        "success": True,
        "data": {"type": 2, "content": "请稍等（云之家不能streaming push）"}
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=9999)
