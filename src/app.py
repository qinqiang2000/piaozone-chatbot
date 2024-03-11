#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
import os
import time
from typing import Optional,Any
import sys
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root_dir)
import asyncio
from collections import deque

import httpcore
import traceback
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Request, Query, File, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from starlette.background import BackgroundTasks

from config.settings import *
from src.sync.sync_flow import SyncFlow
from src.utils.logger import logger
from src.utils.manage_config import ConfigManager
from src.handlers.yunzhijia_handler import YZJHandler, YJZRobotMsg, YQMsg, AsstMsg

class App(FastAPI):
    def __init__(self, **extra: Any):
        super().__init__(**extra)
        # 1. 初始化 config
        self.config_manager = ConfigManager(yuque_base_url=YUQUE_BASE_URL, yuque_namespace=YUQUE_NAMESPACE,
                                       yuque_auth_token=YUQUE_AUTH_TOKEN, yuque_request_agent=YUQUE_REQUEST_AGENT,
                                       config_repo=CONFIG_REPO, config_slug=CONFIG_SLUG, use_azure=USE_AZURE_OPENAI)

        self.assistants = {}
        yuque_repos = self.config_manager.get_all_yq_repo()
        # 2. 初始化语雀到GPT assistant 的同步组件
        if USE_AZURE_OPENAI:
            logger.info("使用 Azure OpenAI")
            self.asst_sync_flow = SyncFlow(
                yuque_base_url=YUQUE_BASE_URL, yuque_namespace=YUQUE_NAMESPACE,
                yuque_auth_token=YUQUE_AUTH_TOKEN, yuque_request_agent=YUQUE_REQUEST_AGENT,
                sync_destination_name=SYNC_DEST_TYPE[0], file_num_limit=ASSISTANT_FILE_NUM_LIMIT,
                file_token_limit=ASSISTANT_FILE_TOKEN_LIMIT, yuque_repos=yuque_repos,
                api_key=AZURE_OPENAI_API_KEY, azure_endpoint=AZURE_OPENAI_ENDPOINT, api_version=OPENAI_API_VERSION)
            self.get_assistant = self.get_azure_openai_assistant
        else:
            logger.info("使用 OpenAI")
            self.asst_sync_flow = SyncFlow(
                yuque_base_url=YUQUE_BASE_URL, yuque_namespace=YUQUE_NAMESPACE,
                yuque_auth_token=YUQUE_AUTH_TOKEN, yuque_request_agent=YUQUE_REQUEST_AGENT,
                sync_destination_name=SYNC_DEST_TYPE[0], file_num_limit=ASSISTANT_FILE_NUM_LIMIT,
                file_token_limit=ASSISTANT_FILE_TOKEN_LIMIT, yuque_repos=yuque_repos,
                api_key=OPENAI_API_KEY)
            self.get_assistant = self.get_openai_assistant
        logger.info(f"完成语雀到 {SYNC_DEST_TYPE[0]} 的同步流程初始化")
        # 3. 初始化云之家处理器
        self.yzjhandler = YZJHandler(yunzhijia_notify_url=YUNZHIJIA_NOTIFY_URL,
                                     max_img_num_in_card_notice=MAX_IMG_NUM_IN_CARD_NOTICE,
                                     card_notice_template_id=CARD_NOTICE_TEMPLATE_ID,
                                     config_manager=self.config_manager)
        logger.info(f"完成云之家处理器的初始化")
        # 4. 初始化gpt assistants
        self.init_asst()

        self.add_api_route("/chat", self.yzj_fpy_chat, methods=["POST"])
        self.add_api_route("/yuque/webhook", self.yuque_fpy_sync, methods=["POST"])
        self.add_api_route("/yuque/config_update", self.yuque_update_config, methods=["POST"])

        self.add_api_route("/sync", self.force_sync, methods=["POST"])
        self.add_api_route("/update_config", self.update_config, methods=["POST"])
        self.add_api_route("/get_config", self.get_config, methods=["GET"])

    def init_asst(self):
        """初始化assistants"""
        all_asst_ids = self.config_manager.get_all_asst_id()
        for asst_id in all_asst_ids:
            try:
                self.get_assistant(asst_id)
                logger.info(f"初始化assistant '{asst_id}' 成功")
            except Exception as e:
                logger.error(f"初始化assistant '{asst_id}' 失败：{e}")
    def get_openai_assistant(self,assistant_id):
        from src.qa_assistant.openai_assistant import Assistant
        if assistant_id not in self.assistants:
            self.assistants[assistant_id] = Assistant(assistant_id=assistant_id, api_key=OPENAI_API_KEY)
            # 如果不存在文件则上传文件
            if not self.assistants[assistant_id].check_asst_file():
                logger.info(f"assistant '{assistant_id}' 不存在文件，开始同步文件")
                repo, toc_title = self.config_manager.get_yq_info_by_asst_id(assistant_id)
                ret = self.asst_sync_flow.sync_yq_topicdata_to_asst(repo, toc_title, assistant_id)
        return self.assistants[assistant_id]
    def get_azure_openai_assistant(self,assistant_id):
        from src.qa_assistant.azure_openai_assistant import Assistant
        if assistant_id not in self.assistants:
            self.assistants[assistant_id] = Assistant(assistant_id=assistant_id, api_key=AZURE_OPENAI_API_KEY,
                                                   azure_endpoint=AZURE_OPENAI_ENDPOINT, api_version=OPENAI_API_VERSION,
                                                   deployment_name=OPENAI_DEPLOYMENT_NAME)
            # 如果不存在文件则上传文件
            if not self.assistants[assistant_id].check_asst_file():
                repo, toc_title = self.config_manager.get_yq_info_by_asst_id(assistant_id)
                logger.info(f"assistant '{assistant_id}' 不存在文件，开始同步专题库 '{toc_title}' 的文件")
                ret = self.asst_sync_flow.sync_yq_topicdata_to_asst(repo, toc_title, assistant_id)
        return self.assistants[assistant_id]
    async def yzj_fpy_chat(self,request: Request, msg: YJZRobotMsg, task: BackgroundTasks, yzj_token: str = Query(...)):
        """
        云之家对话接口
        :param request:
        :param msg:
        :param task:
        :param yzj_token:
        :return:
        """
        session_id = request.headers.get("sessionId")
        msg.sessionId = session_id
        if not yzj_token:
            logger.error("云之家群聊机器人链接没有配置参数yzj_token")
            return
        # 1、处理消息文本
        msg = self.yzjhandler.process_message(msg)
        # 2、获取assistant
        repo, toc_title, assistant_id = self.config_manager.get_info_by_yzj_token(yzj_token)
        if not assistant_id:
            logger.error(f"没有配置参数yzj_token的相关信息，yzj_token={yzj_token}")
            return
        assistant = self.get_assistant(assistant_id)

        # msg.content包含sync gpt(仍保留)，则同步语雀文档到gpt assistant
        if "sync gpt" in msg.content.lower():
            task.add_task(self.yzjhandler.sync_gpt_assistant_on_yzj, self.asst_sync_flow, yzj_token, msg)
        elif msg.content:
            task.add_task(self.yzjhandler.chat_doc, assistant, yzj_token, msg)
        result = {
            "success": True,
            "data": {"type": 2, "content": "请稍等..."}
        }
        return JSONResponse(content=result)

    async def yuque_fpy_sync(self, msg: YQMsg, task: BackgroundTasks):
        """
        语雀同步信息
        :param msg:
        :param task:
        :return:
        """
        # 检查输入数据
        task.add_task(self.yzjhandler.sync_gpt_assistant_on_yq, self.asst_sync_flow, msg)
        result = {"success": True}
        return JSONResponse(content=result)

    async def force_sync(self, task: BackgroundTasks, assistant_id: str = Query(...)):
        if assistant_id not in self.config_manager.get_all_asst_id() or not assistant_id:
            logger.error(f"不存在assistant_id '{assistant_id}'，请重新输入")
            result = {"success": False, "description": f"不存在assistant_id '{assistant_id}'，请重新输入"}
            return JSONResponse(content=result)
        task.add_task(self.yzjhandler.manual_sync_gpt_assistant, self.asst_sync_flow, assistant_id)
        result = {"success": True, "description": f"正在同步中"}
        return JSONResponse(content=result)

    async def yuque_update_config(self, msg: YQMsg):
        """
        基于语雀消息更新配置信息
        :param msg:
        :return:
        """
        # 检查输入数据
        action_type = msg.data.get("action_type")
        if action_type in ["update"]:
            repo = msg.data["book"]["slug"]
            doc_slug = msg.data["slug"]
            if repo == CONFIG_REPO and doc_slug == CONFIG_SLUG:
                logger.info("开始更新配置...")
                try:
                    add_repo, del_repo, add_asst, del_asst = self.config_manager.update_config()
                    #
                    if add_asst:
                        for asst_id in add_asst:
                            self.get_assistant(asst_id)
                            logger.debug(f"初始化assistant '{asst_id}' 成功")
                    if add_repo:
                        self.asst_sync_flow.update_sync_config(add_repo)
                    logger.info(f"配置更新成功")
                except:
                    logger.error(f"配置更新失败，请重新尝试")
        result = {"success": True}
        return JSONResponse(content=result)
    async def update_config(self):
        """
        更新配置信息
        :return:
        """
        result = {"success": False}
        try:
            add_repo, del_repo, add_asst, del_asst = self.config_manager.update_config()
            #
            if add_asst:
                for asst_id in add_asst:
                    self.get_assistant(asst_id)
                    logger.debug(f"初始化assistant '{asst_id}' 成功")
            if add_repo:
                self.asst_sync_flow.update_sync_config(add_repo)
            logger.info(f"配置更新成功")
            result = {"success": True}
        except:
            logger.error(f"配置更新失败，请重新尝试")
        return JSONResponse(content=result)
    async def get_config(self):
        result = {"data": self.config_manager.config_data}
        return JSONResponse(content=result)





if __name__ == "__main__":
    import uvicorn

    app = App()
    uvicorn.run(app, host="0.0.0.0", port=9999)
