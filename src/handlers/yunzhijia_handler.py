"""
============================
# -*- coding: utf-8 -*-
# @Time    : 2024/1/16 15:29
# @Author  : LinLimin
# @Desc    : 用于处理云之家消息的handler
===========================
"""
from typing import Optional
import requests

from pydantic import BaseModel
import httpcore

from qa_assistant.base_assistant import BaseAssistant
from src.utils.logger import logger
from src.utils.data_process import (
    parse_img_urls,
    remove_html_tags)

class YZJRobotMsg(BaseModel):
    type: int
    robotId: Optional[str] = None
    robotName: Optional[str] = None
    operatorName: Optional[str] = None
    msgId: Optional[str] = None
    operatorOpenid: str = None
    content: str = None
    time: int
    sessionId: Optional[str] = None

class YQMsg(BaseModel):
    data: Optional[dict] = None


class YZJHandler:
    HANDLER_TYPE = "yunzhijia"
    def __init__(self, yunzhijia_config, config_manager):
        self.yunzhijia_notify_url = yunzhijia_config["notify_url"]
        self.max_img_num_in_card_notice = yunzhijia_config["max_img_num_in_card_notice"]
        self.card_notice_template_id = yunzhijia_config["card_notice_template_id"]
        self.config_manager = config_manager
        logger.info(f"云之家处理器的初始化成功")

    def process_message(self, yzj_message: YZJRobotMsg):
        # 处理云之家消息
        # 取yzj_message.content第一个空格之后的消息
        logger.info(f"[{yzj_message.robotId}~{yzj_message.operatorOpenid}]:未处理前消息： {yzj_message.content}")
        yzj_message.content = " ".join(yzj_message.content.split()[1:])
        # 去除yzj_message.content中的前后空格
        yzj_message.content = yzj_message.content.strip()
        logger.info(f"[{yzj_message.robotId}~{yzj_message.operatorOpenid}]: {yzj_message}")
        return yzj_message

    def send_yzj_card_notice(self, yzj_token, img_urls, operator_open_id):
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
        card_num = int(img_num / self.max_img_num_in_card_notice)
        # 图片数量不能被max_img_num_in_card_notice整除，则需要卡片数+1
        if img_num % self.max_img_num_in_card_notice != 0:
            card_num += 1
        for i in range(card_num):
            data_content = self.gen_card_notice_data_content(img_urls, img_num, card_num, i)
            # 卡片填充信息
            param = {"baseInfo": {"templateId": self.card_notice_template_id, "dataContent": str(data_content)}}
            # 当需要at人员时传入
            notify_params = [{"type": "openIds", "values": [operator_open_id]}]
            url = self.yunzhijia_notify_url.format(yzj_token)
            logger.info(f"请求云之家发送图片信息以卡片通知消息形式,地址:{url} 图片内容{img_urls}")
            resp = requests.post(url, json={"msgType": 2, "param": param, "notifyParams": notify_params},
                                 headers={'Content-Type': 'application/json'})
            logger.info(f"请求云之家发送图片信息以卡片通知消息形式结束,返回消息：{resp}")

    def gen_card_notice_data_content(self, img_urls, img_num, card_num, index):
        """
        根据图片构建卡片消息data_content
        :param img_urls:
        :param img_num:
        :param card_num:
        :param index:
        :return:
        """
        data_content = {}
        img_num_in_card = self.max_img_num_in_card_notice
        if index == card_num - 1:
            img_num_in_card = img_num % self.max_img_num_in_card_notice
        for j in range(img_num_in_card):
            img_url = img_urls[j + index * self.max_img_num_in_card_notice]
            if j == 0:
                data_content["bigImageUrl"] = img_url
            else:
                data_content[f"bigImage{j}Url"] = img_url
        return data_content

    def chat_doc(self, qa_assistant, yzj_token, msg: YZJRobotMsg):
        """
        调用问答助手获取答案
        :param qa_assistant:
        :param yzj_token:
        :param msg:
        :return:
        """
        output = "抱歉，大模型响应超时，请稍后再试"
        session_id = msg.sessionId
        logger.debug(f"[asst_id={qa_assistant.assistant_id}]:额外参数 robotId={msg.robotId};robotName={robotName};operatorName={operatorName};msgId={msgId}")
        try:
            if not msg.content.strip():
                output = "抱歉，输入内容为空，请输入有效内容"
            else:
                answer = qa_assistant.chat(session_id, msg.content)
                if answer:
                    output = answer
        except:
            logger.error(f"大模型响应超时，session_id: {session_id}")
        logger.info(f"[asst_id={qa_assistant.assistant_id};session_id={session_id}; operatorOpenid={msg.operatorOpenid}] --> {output} ")
        # 先截取图片url
        img_urls = parse_img_urls(output)
        # 去掉html标签
        output = remove_html_tags(output)
        if img_urls:
            output += "\n具体图片可参考下面一条消息所示："
        data = {"content": output,
                "notifyParams": [{"type": "openIds", "values": [msg.operatorOpenid]}]}
        requests.post(self.yunzhijia_notify_url.format(yzj_token), json=data)

        if img_urls:
            self.send_yzj_card_notice(yzj_token, img_urls, msg.operatorOpenid)

        logger.debug(
            f"[asst_id={qa_assistant.assistant_id};session_id={session_id}; operatorOpenid={msg.operatorOpenid}]: 回答结束")

    def sync_gpt_assistant_on_yzj(self, sync_flow, yzj_token, assistant: BaseAssistant, msg: YZJRobotMsg):
        """
        基于云之家的消息，同步知识库数据到gpt assistant，同时通知云之家
        :param sync_flow:
        :param yzj_token:
        :param assistant:
        :param msg:
        :return:
        """
        success = "成功"
        repo, toc_title, assistant_id = self.config_manager.get_info_by_yzj_token(yzj_token)

        ret = sync_flow.sync_yq_doc_to_dest(repo, toc_title, assistant)
        if ret:
            logger.info(f"同步知识库'{toc_title}'数据到gpt assistant成功: {assistant_id}")
        else:
            success = "失败"

        data = {"content": f"同步最新文档至Assistant{success}",
                "notifyParams": [{"type": "openIds", "values": [msg.operatorOpenid]}]}
        requests.post(self.yunzhijia_notify_url.format(yzj_token), json=data)
    def manual_sync_gpt_assistant(self, sync_flow, assistant):
        """
        手动同步，同步知识库数据到gpt assistant，同时通知云之家
        :param sync_flow:
        :param msg:
        :return:
        """
        assistant_id = assistant.assistant_id
        repo, toc_title = self.config_manager.get_yq_info_by_asst_id(assistant_id)
        yzj_tokens = self.config_manager.get_yzj_token_by_asst_id(assistant_id)
        logger.info(f"语雀知识库'{toc_title}' 需要同步至gpt assistant: '{assistant_id}'")
        # 通知云之家需要开始同步
        start_data = {"content": f"开始同步新文档至Assistant,如果有什么问题请同步结束后再提问。"}
        for yzj_token in yzj_tokens:
            requests.post(self.yunzhijia_notify_url.format(yzj_token), json=start_data)
        # 同步知识库数据到gpt assistant
        ret = sync_flow.sync_yq_doc_to_dest(repo, toc_title, assistant)
        success = "成功"
        if ret:
            logger.info(f"同步知识库'{toc_title}'数据到gpt assistant成功: {assistant_id}")
        else:
            success = "失败"
        # 通知云之家同步结束
        data = {"content": f"同步最新文档至Assistant{success}。"}
        for yzj_token in yzj_tokens:
            requests.post(self.yunzhijia_notify_url.format(yzj_token), json=data)
        return success


