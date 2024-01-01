import os.path
import time
from typing import Optional

import httpcore
import requests
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Request, Query, File, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from starlette.background import BackgroundTasks

from assistant import Assistant
from common_utils import *
from config.settings import *
import sync.sync_flow as sf

app = FastAPI()
scheduler = AsyncIOScheduler()
assistants = {}


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


def get_assistant(id):
    if id not in assistants:
        assistants[id] = Assistant(id)
    return assistants[id]


@app.on_event("startup")
async def startup_event():
    # 启动定时任务：同步语雀文档到gpt assistant
    # scheduler.add_job(yuque_utils.sync_yuque_docs_2_assistant, CronTrigger(hour=2))
    # scheduler.start()
    logging.info("定时任务暂不启动")


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
    # 先截取图片url
    img_urls = parse_img_urls(output)
    # 去掉html标签
    output = remove_html_tags(output)
    if img_urls:
        output += "\n具体图片可参考下面一条消息所示："
    data = {"content": output,
            "notifyParams": [{"type": "openIds", "values": [msg.operatorOpenid]}]}
    requests.post(YUNZHIJIA_NOTIFY_URL.format(yzj_token), json=data)

    if img_urls:
        send_yzj_card_notice(yzj_token, img_urls, msg.operatorOpenid)


def send_yzj_card_notice(yzj_token, img_urls, operator_open_id):
    """
    发送云之家图片卡片消息
    :param yzj_token:
    :param img_urls:
    :param operator_open_id:
    :return:
    """
    if not img_urls:
        return
    img_num = len(img_urls)
    card_num = int(img_num / MAX_IMG_NUM_IN_CARD_NOTICE)
    # 图片数量不能被MAX_IMG_NUM_IN_CARD_NOTICE整除，则需要卡片数+1
    if img_num % MAX_IMG_NUM_IN_CARD_NOTICE != 0:
        card_num += 1
    for i in range(card_num):
        data_content = gen_card_notice_data_content(img_urls, img_num, card_num, i)
        # 卡片填充信息
        param = {"baseInfo": {"templateId": CARD_NOTICE_TEMPLATE_ID, "dataContent": str(data_content)}}
        # 当需要at人员时传入
        notify_params = [{"type": "openIds", "values": [operator_open_id]}]
        url = YUNZHIJIA_NOTIFY_URL.format(yzj_token)
        logging.info(f"请求云之家发送图片信息以卡片通知消息形式,地址:{url} 图片内容{img_urls}")
        resp = requests.post(url, json={"msgType": 2, "param": param, "notifyParams": notify_params},
                             headers={'Content-Type': 'application/json'})
        logging.info(f"请求云之家发送图片信息以卡片通知消息形式结束,返回消息：{resp}")


def gen_card_notice_data_content(img_urls, img_num, card_num, index):
    """
    根据图片构建卡片消息data_content
    :param img_urls:
    :param img_num:
    :param card_num:
    :param index:
    :return:
    """
    data_content = {}
    img_num_in_card = MAX_IMG_NUM_IN_CARD_NOTICE
    if index == card_num - 1:
        img_num_in_card = img_num % MAX_IMG_NUM_IN_CARD_NOTICE
    for j in range(img_num_in_card):
        img_url = img_urls[j + index * MAX_IMG_NUM_IN_CARD_NOTICE]
        if j == 0:
            data_content["bigImageUrl"] = img_url
        else:
            data_content[f"bigImage{j}Url"] = img_url
    return data_content


def sync_gpt_assistant(yzj_token, msg: RobotMsg):
    success = "成功"
    if "sync gpt cache" in msg.content.lower():
        ret = sf.sync_gpt_by_yzj_cache_flow(yzj_token)
    else:
        ret = sf.sync_gpt_from_yq(yzj_token)
    if not ret:
        success = "失败"

    data = {"content": f"同步最新文档至Assistant{success}",
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
    # 去除msg.content中的前后空格
    msg.content = msg.content.strip()
    logging.info(f"[{msg.robotId + '~' + msg.operatorOpenid}]: {msg}")

    gpt_assistant_id = get_assistant_id_by_yzj_token(yzj_token)
    assistant = get_assistant(gpt_assistant_id)

    # msg.content包含sync gpt，则同步语雀文档到gpt assistant
    if "sync gpt" in msg.content.lower():
        task.add_task(sync_gpt_assistant, yzj_token, msg)
    elif msg.content:
        task.add_task(chat_doc, assistant, yzj_token, msg)

    return {
        "success": True,
        "data": {"type": 2, "content": "请稍等..."}
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=9999)
