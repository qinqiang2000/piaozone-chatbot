"""
============================
# -*- coding: utf-8 -*-
# @Time    : 2024/1/16 15:29
# @Author  : LinLimin
# @Desc    : 用于处理云之家消息的handler
===========================
"""
from typing import Optional,Dict,Any
from pydantic import BaseModel
from src.utils.logger import logger



class ZCRobotMsg(BaseModel):
    cid: str
    msgid: str
    query_txt: str
    partnerid: str
    multi_params: Optional[Any] = None



class ZhiChiHandler:
    HANDLER_TYPE = "zhichi"
    def __init__(self, config_manager):
        self.config_manager = config_manager
        logger.info(f"智齿处理器的初始化成功")

    def chat_doc(self, qa_assistant, msg: ZCRobotMsg, is_auto_entry=False):
        """
        调用问答助手获取答案
        :param qa_assistant:
        :param msg:
        :return:
        """
        output = "抱歉，大模型响应超时，请稍后再试"
        session_id = msg.cid
        has_answer = False
        try:
            if not msg.query_txt.strip():
                output = "抱歉，输入内容为空，请输入有效内容"
            else:
                answer, has_answer = qa_assistant.chat(session_id, msg.query_txt)
                if answer:
                    output = answer
        except Exception as e:
            logger.error(f"大模型响应超时，zhichi session_id '{session_id}':{e}")
        logger.info(f"[asst_id={qa_assistant.assistant_id};zhichi_session_id={session_id}]回答内容: {output} ")
        try:
            if is_auto_entry:
                yq_info = self.config_manager.get_yq_info_by_asst_id(qa_assistant.assistant_id)
                topic_name = '-'.join([title for _, title in yq_info])
                qa_assistant.save_faq_to_database(topic_name=topic_name,
                                                  question=msg.query_txt,
                                                  answer=output,
                                                  has_answer=has_answer,
                                                  asker="")
        except:
            logger.error(f"[asst_id={qa_assistant.assistant_id};zhichi_session_id={session_id}]自动问答记录失败")
        return output, has_answer



