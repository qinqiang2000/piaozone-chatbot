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
        try:
            robotName = yzj_message.robotName
            yzj_message.content = yzj_message.content.replace(f"@{robotName}", '')
            # 去除yzj_message.content中的前后空格
            yzj_message.content = yzj_message.content.strip()
            logger.debug(f"[yzj_robot_id={yzj_message.robotId}]: {yzj_message}")
        except Exception as e:
            logger.error(f"云之家消息处理失败，错误信息：{e}")
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

    def chat_doc(self, qa_assistant, yzj_token, msg: YZJRobotMsg, is_auto_entry=False):
        """
        调用问答助手获取答案
        :param qa_assistant:
        :param yzj_token:
        :param msg:
        :return:
        """
        output = "抱歉，大模型响应超时，请稍后再试"
        session_id = msg.sessionId
        has_answer = False
        try:
            if not msg.content.strip():
                output = "抱歉，输入内容为空，请输入有效内容"
            else:
                answer, has_answer = qa_assistant.chat(session_id, msg.content)
                if answer:
                    output = answer
        except Exception as e:
            logger.error(f"大模型响应超时，yzj session_id '{session_id}':{e}")
        logger.info(f"[asst_id={qa_assistant.assistant_id};yzj_session_id={session_id}]回答内容: {output} ")

        try:
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
        except Exception as e:
            logger.error(f"云之家消息处理失败，错误信息：{e}")

        #获取需要的信息并录入到数据库：
        if is_auto_entry:
            yq_info = self.config_manager.get_yq_info_by_yzj_token(yzj_token)
            topic_name = '-'.join([title for _, title in yq_info])
            qa_assistant.save_faq_to_database(topic_name=topic_name,
                                              question=msg.content,
                                              answer=output,
                                              has_answer=has_answer,
                                              asker=msg.operatorName)



    def notice_yzj_group(self, yzj_token, content):
        start_data = {"content": content}
        requests.post(self.yunzhijia_notify_url.format(yzj_token), json=start_data)


