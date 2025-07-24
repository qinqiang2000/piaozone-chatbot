"""
============================
# -*- coding: utf-8 -*-
# @Time    : 2024/1/16 15:29
# @Author  : LinLimin
# @Desc    : 用于简单聊天
===========================
"""
from typing import Optional
from pydantic import BaseModel
from src.utils.logger import logger
from src.utils.constants import QSource


class SimpleMsg(BaseModel):
    session_id: str
    assistant_id: str
    message: str
    msg_id: Optional[str] = None



class SimpleHandler:
    HANDLER_TYPE = QSource.OTHER
    def __init__(self, config_manager,database):
        self.config_manager = config_manager
        self.database = database
        self.qa_headers = ["session_id", "msg_id", "question", "answer", "has_answer", "feedback", "created_at"]
        self.qa_headers_zh = ["会话id", "消息id", "问题", "答案", "是否存在答案", "反馈状态", "创建时间"]

        logger.info(f"智齿处理器的初始化成功")

    def chat(self, qa_assistant, msg: SimpleMsg):
        """
        调用问答助手获取答案
        :param qa_assistant:
        :param msg:
        :return:
        """
        output = "抱歉，大模型响应超时，请稍后再试"
        session_id = msg.session_id
        try:
            if not msg.message.strip():
                output = "抱歉，输入内容为空，请输入有效内容"
            else:
                answer, _ = qa_assistant.chat(session_id, msg.message)
                if answer:
                    output = answer
        except Exception as e:
            logger.error(f"大模型响应超时，other session_id '{session_id}':{e}")
        logger.info(f"[asst_id={qa_assistant.assistant_id};other_session_id={session_id}]回答内容: {output} ")
        return output




