"""
============================
# -*- coding: utf-8 -*-
# @Time    : 2024/1/16 15:29
# @Author  : LinLimin
# @Desc    : 用于处理云之家消息的handler
===========================
"""
import random
import string
from typing import Optional
from pydantic import BaseModel
from src.utils.celery_app import celery_app
from qa_assistant.base_assistant import BaseAssistant
from src.utils.logger import logger
from src.utils.data_process import (
    parse_img_urls,
    remove_html_tags)


class BaseMsg(BaseModel):
    content: str = None
    assistant_id: str = None
    session_id: Optional[str] = None


class BaseHandler:
    HANDLER_TYPE = "base"
    def __init__(self, config_manager,assistans):
        self.config_manager = config_manager
        BaseHandler.assistans = assistans
        logger.info(f"基础处理器的初始化成功")

    @staticmethod
    def process_message(content):
        content = content.strip()
        return content

    @staticmethod
    def generate_random_string(length):
        # 定义可能的字符集合，可以包括大小写字母和数字
        characters = string.ascii_letters + string.digits
        # 使用random.choices随机选择字符，生成指定长度的字符串
        random_string = ''.join(random.choices(characters, k=length))
        return random_string

    @staticmethod
    @celery_app.task
    def chat_doc(msg_dict):
        """
        调用问答助手获取答案
        :param qa_assistant:
        :param yzj_token:
        :param msg:
        :return:
        """
        output = "抱歉，大模型响应超时，请稍后再试"
        try:
            assistant_id = msg_dict['assistant_id']
            qa_assistant = BaseHandler.assistans.get(assistant_id,None)
            if qa_assistant is None:
                return "没有输入有效的assistant_id"

            if not msg_dict.get('session_id',None):
                session_id = BaseHandler.generate_random_string(10)
            else:
                session_id = msg_dict['session_id']
            content = BaseHandler.process_message(msg_dict['content'])
            if not content:
                output = "抱歉，输入内容为空，请输入有效内容"
            else:
                answer = qa_assistant.chat(session_id, content)
                if answer:
                    output = answer
        except:
            logger.error(f"大模型响应超时，session_id: {session_id}")
        logger.info(f"[session_id={session_id}]--> {output}")
        # 去掉html标签
        output = remove_html_tags(output)
        return output



