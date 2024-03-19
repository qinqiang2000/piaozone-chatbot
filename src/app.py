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
        self.config_manager = ConfigManager(
            yuque_base_url=YUQUE_BASE_URL,
            yuque_namespace=YUQUE_NAMESPACE,
            yuque_auth_token=YUQUE_AUTH_TOKEN,
            yuque_request_agent=YUQUE_REQUEST_AGENT,
            config_repo=CONFIG_REPO,
            config_slug=CONFIG_SLUG,
            use_azure=USE_AZURE_OPENAI)

        # 2. 初始化语雀到GPT assistant 的同步组件
        yuque_repos = self.config_manager.get_all_yq_repo()
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
        # 3. 初始化云之家处理器
        self.yzjhandler = YZJHandler(yunzhijia_notify_url=YUNZHIJIA_NOTIFY_URL,
                                     max_img_num_in_card_notice=MAX_IMG_NUM_IN_CARD_NOTICE,
                                     card_notice_template_id=CARD_NOTICE_TEMPLATE_ID,
                                     config_manager=self.config_manager)
        # 4. 初始化gpt assistants
        self.init_asst()

        # 5、添加定时任务,每周6 2点触发定时任务
        self.add_event_handler("startup", self.startup_tasks)
        self.add_event_handler("shutdown", self.shutdown_tasks)
        # 6、初始化定时同步锁
        # self.pending_syncs_lock = asyncio.Lock()
        # self.pending_syncs = set()

        # 7、添加 api_route
        self.add_api_route("/chat", self.yzj_fpy_chat, methods=["POST"])
        # self.add_api_route("/yuque/webhook", self.yuque_sync_info_update, methods=["POST"])
        self.add_api_route("/yuque/config_update", self.yuque_update_config, methods=["POST"])
        self.add_api_route("/sync", self.force_sync, methods=["POST"])
        self.add_api_route("/update_config", self.force_update_config, methods=["POST"])
        self.add_api_route("/get_config", self.get_config, methods=["GET"])

    def init_asst(self) -> None:
        """初始化assistants"""
        self.assistants = {}
        all_asst_ids = self.config_manager.get_all_asst_id()
        for asst_id in all_asst_ids:
            try:
                asst = self.get_assistant(asst_id)
                if asst is not None:
                    logger.info(f"初始化assistant '{asst_id}' 成功")
                else:
                    logger.info(f"同步不成功，初始化assistant '{asst_id}' 失败")
            except Exception as e:
                logger.error(f"初始化assistant '{asst_id}' 失败：{e}")
    def get_openai_assistant(self,assistant_id: str):
        from src.qa_assistant.openai_assistant import Assistant
        if assistant_id not in self.assistants:
            self.assistants[assistant_id] = Assistant(assistant_id=assistant_id, api_key=OPENAI_API_KEY)
            # 如果不存在文件则上传文件
            if not self.assistants[assistant_id].check_asst_file():
                logger.info(f"assistant '{assistant_id}' 不存在文件，开始同步文件")
                repo, toc_title = self.config_manager.get_yq_info_by_asst_id(assistant_id)
                ret = self.asst_sync_flow.sync_yq_topicdata_to_asst(repo, toc_title, assistant_id)
                # 如果同步失败：
                if not ret:
                    return None
        return self.assistants[assistant_id]
    def get_azure_openai_assistant(self,assistant_id: str):
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
                # 如果同步失败：
                if not ret:
                    return None
        return self.assistants[assistant_id]
    def update_config(self) -> None:
        """更新配置"""
        logger.info("开始更新配置...")
        try:
            add_repo, del_repo, add_asst, del_asst = self.config_manager.update_config()
            #
            if add_repo:
                self.asst_sync_flow.update_sync_config(add_repo)
            if add_asst:
                for asst_id in add_asst:
                    asst = self.get_assistant(asst_id)
                    if asst is not None:
                        logger.info(f"初始化assistant '{asst_id}' 成功")
                    else:
                        logger.info(f"同步不成功，初始化assistant '{asst_id}' 失败")
        except Exception as e:
            logger.error(f"配置更新失败：{e}.{traceback.format_exc()}")
    async def yzj_fpy_chat(self,request: Request, msg: YJZRobotMsg,
                           task: BackgroundTasks, yzj_token: str = Query(...)) -> JSONResponse:
        """
        云之家对话接口
        :param request: 请求对象
        :param msg: 云之家机器人消息
        :param task: 后台任务
        :param yzj_token: 云之家群聊机器人链接参数
        :return: JSON响应
        """
        try:
            session_id = request.headers.get("sessionId")
            msg.sessionId = session_id
            if not yzj_token:
                logger.error("云之家群聊机器人链接没有配置参数yzj_token")
                result = {
                    "success": False,
                    "data": {"type": 2, "content": "云之家群聊机器人链接没有配置参数yzj_token"}
                }
                return JSONResponse(content=result)
            # 1、处理消息文本
            msg = self.yzjhandler.process_message(msg)
            # 2、获取assistant
            repo, toc_title, assistant_id = self.config_manager.get_info_by_yzj_token(yzj_token)
            if not assistant_id:
                logger.error(f"没有配置参数yzj_token的相关信息，yzj_token={yzj_token}")
                result = {
                    "success": True,
                    "data": {"type": 2, "content": "没有配置知识库信息，请配置完再提问"}
                }
                return JSONResponse(content=result)
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
        except Exception as e:
            logger.error(f"[yzj_token={yzj_token}] 出现错误:{e}.{traceback.format_exc()}")
            result = {
                "success": True,
                "data": {"type": 2, "content": "抱歉，目前存在问题，请稍后再试"}
            }
        return JSONResponse(content=result)

    # async def yuque_sync_info_update(self, msg: YQMsg) -> JSONResponse:
    #     """
    #     更新语雀定时同步信息
    #     :param msg: 语雀消息对象
    #     :return: JSON响应
    #     """
    #     try:
    #         action_type = msg.data.get("action_type")
    #         if action_type in ["publish", "update", "delete"]:
    #             repo = msg.data["book"]["slug"]
    #             # doc_slug = msg.data["slug"]
    #             doc_id = msg.data["id"]
    #             # 获取文档所在的专题库的标题
    #             toc_title, _ = self.asst_sync_flow.yqreader.get_topic_title_for_single_doc(repo, doc_id, action_type)
    #             yzj_tokens, assistant_id = self.config_manager.get_yzj_token_and_asst_id_by_yq_info(repo, toc_title)
    #             if assistant_id is not None:
    #                 async with self.pending_syncs_lock:
    #                     if assistant_id not in self.pending_syncs:
    #                         self.pending_syncs.add(assistant_id)
    #                         logger.info(
    #                             f"语雀知识库'{toc_title}' 中的文档 '{msg.data['title']}' 进行了 '{action_type}' 操作，需要同步至gpt assistant: '{assistant_id}'")
    #             else:
    #                 logger.info(f"语雀知识库'{toc_title}'没有关联的gpt assistant,不需要同步")
    #         else:
    #             logger.info(f"文档'{msg.data['title']}'进行了 '{action_type}' 操作，不需要同步")
    #         result = {"success": True}
    #     except Exception as e:
    #         result = {"success": False}
    #         logger.error(f"语雀知识库定时同步信息更新失败：{e}.{traceback.format_exc()}")
    #     return JSONResponse(content=result)


    async def force_sync(self, task: BackgroundTasks, assistant_id: str = Query(...)) -> JSONResponse:
        try:
            if assistant_id not in self.config_manager.get_all_asst_id() or not assistant_id:
                logger.error(f"不存在assistant_id '{assistant_id}'，请重新输入")
                result = {"success": False, "description": f"不存在assistant_id '{assistant_id}'，请重新输入"}
                return JSONResponse(content=result)
            task.add_task(self.yzjhandler.manual_sync_gpt_assistant, self.asst_sync_flow, assistant_id)
            result = {"success": True, "description": f"正在同步中"}
            return JSONResponse(content=result)
        except Exception as e:
            result = {"success": False, "description": str(e)}
            logger.error(f"{assistant_id} 助手同步失败：{e}.{traceback.format_exc()}")
            return JSONResponse(content=result)

    async def async_manual_sync(self, assistant_id):
        """
        定时同步: 包装同步函数为异步函数
        """
        try:
            result = await asyncio.get_running_loop().run_in_executor(
                None, self.yzjhandler.manual_sync_gpt_assistant, self.asst_sync_flow, assistant_id
            )
        except Exception as e:
            logger.error(f"同步助手 '{assistant_id}' 失败：{e}")

    async def scheduler_sync(self):
        logger.info("开始执行定时任务")
        tasks = []
        semaphore = asyncio.Semaphore(10)   # 设置并发执行的任务数量
        for assistant_id in self.config_manager.get_all_asst_id():
            if not assistant_id:
                logger.warning(f"不存在assistant_id '{assistant_id}'")
            else:
                async with semaphore:
                    task = asyncio.create_task(self.async_manual_sync(assistant_id))
                    tasks.append(task)
        # 等待所有后台任务完成
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("定时任务结束")
    async def startup_tasks(self):
        """
        在结束时同步并关闭定时器
        """
        self.scheduler = AsyncIOScheduler()
        self.scheduler.add_job(self.scheduler_sync, 'cron', day_of_week='sat', hour=2)
        self.scheduler.start()
        logger.info("设置定时同步任务成功")
    async def shutdown_tasks(self):
        """
        在结束时同步并关闭定时器
        """
        self.scheduler.shutdown()
        logger.debug("关闭程序")

    async def yuque_update_config(self, msg: YQMsg, task: BackgroundTasks):
        """
        基于语雀消息更新配置信息
        :param msg:
        :return:
        """
        try:
            # 检查输入数据
            action_type = msg.data.get("action_type")
            if action_type in ["update"]:
                repo = msg.data["book"]["slug"]
                doc_slug = msg.data["slug"]
                if repo == CONFIG_REPO and doc_slug == CONFIG_SLUG:
                    task.add_task(self.update_config)
            result = {"success": True}
        except Exception as e:
            result = {"success": False}
            logger.error(f"语雀文档配置更新失败：{e}.{traceback.format_exc()}")
        return JSONResponse(content=result)
    async def force_update_config(self, task: BackgroundTasks):
        """
        更新配置信息
        :return:
        """
        try:
            task.add_task(self.update_config)
            result = {"success": True, "description": f"正在更新配置"}
        except Exception as e:
            result = {"success": False, "description": str(e)}
            logger.error(f"配置更新失败：{e}.{traceback.format_exc()}")
        return JSONResponse(content=result)
    async def get_config(self):
        try:
            result = {"success": True, "description": "操作成功",
                      "data": self.config_manager.config_data}
        except Exception as e:
            result = {"success": False, "description": str(e)}
            logger.error(f"获取配置失败：{e}.{traceback.format_exc()}")
        return JSONResponse(content=result)





if __name__ == "__main__":
    import uvicorn

    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["formatters"]["access"]["fmt"] = "[%(asctime)s %(filename)s:%(lineno)d] %(levelname)s: %(message)s"
    log_config["formatters"]["default"]["fmt"] = "[%(asctime)s %(filename)s:%(lineno)d] %(levelname)s: %(message)s"

    app = App()
    uvicorn.run(app, host="0.0.0.0", port=9999, log_config=log_config)