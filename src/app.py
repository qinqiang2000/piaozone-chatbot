#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
import asyncio
import os
from typing import Any
import sys

import traceback
import threading
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request, Query
from fastapi.responses import JSONResponse
from starlette.background import BackgroundTasks
from celery.result import AsyncResult
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root_dir)
from config.settings import *
from src.utils.logger import logger
from src.utils.manage_config import ConfigManager
from src.sync.sync_flow_manger import SyncManager
from src.handlers.yunzhijia_handler import YZJHandler, YZJRobotMsg, YQMsg
from src.qa_assistant.base_assistant import ASSTType
from src.utils.database import SQLDatabase, FAQ
import datetime
from sqlalchemy import and_
import requests

class App(FastAPI):
    """
    知识库问答助手应用
    """
    def __init__(self, **extra: Any):
        super().__init__(**extra)
        # 1. 初始化 config
        self.config_manager = ConfigManager(
            yuque_config=YUQUE_CONFIG,
            config_repo=CONFIG_REPO,
            config_slug=CONFIG_SLUG)

        # 2. 初始化语雀到assistant 或者其他的同步组件
        yuque_repos = self.config_manager.get_all_yq_repo()
        self.sync_manager = SyncManager(yuque_config=YUQUE_CONFIG,yuque_repos=yuque_repos,sync_configs=SYNC_CONFIGS)

        # 3. 初始化数据库
        self.database = SQLDatabase(**DB_CONFIG)
        self.database.create_table(table_class=FAQ) #建表储存问答信息


        # 4. 初始化gpt assistants
        self.init_asst()

        # 5. 初始化云之家处理器和基础配置管理器
        self.yzjhandler = YZJHandler(yunzhijia_config=YUNZHIJIA_CONFIG,
                                     config_manager=self.config_manager)

        # 6、添加定时任务,每周6 2点触发定时任务
        self.add_event_handler("startup", self.startup_tasks)
        self.add_event_handler("shutdown", self.shutdown_tasks)

        # 7、添加 api_route
        self.add_api_route("/chat", self.yzj_fpy_chat, methods=["POST"])
        # self.add_api_route("/yuque/webhook", self.yuque_sync_info_update, methods=["POST"])
        self.add_api_route("/yuque/config_update", self.yuque_update_config, methods=["POST"])
        self.add_api_route("/sync", self.force_sync, methods=["POST"])
        self.add_api_route("/empty_file", self.empty_files, methods=["POST"])
        self.add_api_route("/update_config", self.force_update_config, methods=["POST"])
        self.add_api_route("/get_config", self.get_config, methods=["GET"])


    def init_asst(self) -> None:
        """初始化assistants"""
        self.assistants = {}
        all_asst_ids = self.config_manager.get_all_asst_id()
        for asst_id in all_asst_ids:
            try:
                asst = self.get_assistant(assistant_id=asst_id)
                if asst is not None:
                    logger.info(f"[asst_id={asst_id}]: 初始化助手成功")
                else:
                    logger.info(f"[asst_id={asst_id}]: 同步不成功，初始化助手失败")
            except Exception as e:
                logger.error(f"[asst_id={asst_id}]: 初始化助手失败：{e}")
    def get_assistant(self,assistant_id):
        asst_type, llm_type = self.config_manager.get_asst_info_by_asst_id(assistant_id)
        repo, toc_title = self.config_manager.get_yq_info_by_asst_id(assistant_id)
        topic = repo + "_" + toc_title
        if asst_type == ASSTType.NATIVE_ASST:
            return self.get_openai_assistant(assistant_id, llm_type, asst_type, topic)
        else:
            logger.error(f"不支持的助手类型: {asst_type}")
            return None
    def get_openai_assistant(self,assistant_id: str, llm_type: str, asst_type: int,topic: str):
        from src.qa_assistant.openai_assistant import Assistant as OpenAIAssistant
        if assistant_id not in self.assistants:
            asst_config = ASSISTANT_CONFIG[asst_type].copy()
            asst_config["llm_option"] = llm_type
            self.assistants[assistant_id] = OpenAIAssistant(assistant_id=assistant_id,
                                                            assistant_config=asst_config,
                                                            topic=topic,
                                                            database=self.database)
            # 如果不存在文件则上传文件
            if not self.assistants[assistant_id].check_asst_file():
                repo, toc_title = self.config_manager.get_yq_info_by_asst_id(assistant_id)
                logger.info(f"[asst_id={assistant_id}]: 助手不存在文件，开始同步专题库 '{toc_title}' 的文件")
                sync_id = asst_config['sync_flow_config']['id']
                ret = self.sync_manager.sync_dict[sync_id].sync_yq_doc_to_dest(repo, toc_title, self.assistants[assistant_id])
                # 如果同步失败：
                if not ret:
                    return None
        return self.assistants[assistant_id]


    def update_config(self) -> None:
        """更新配置"""
        logger.info("开始更新配置...")
        try:
            add_repo, _, add_asst, _ = self.config_manager.update_config()
            #
            if add_repo:
                self.sync_manager.update_yq_repos(add_repo)
            if add_asst:
                for asst_id in add_asst:
                    asst = self.get_assistant(asst_id)
                    if asst is not None:
                        logger.info(f"[asst_id={asst_id}]：初始化助手成功")
                    else:
                        logger.info(f"[asst_id={asst_id}]：同步不成功，初始化助手失败")
        except Exception as e:
            logger.error(f"配置更新失败：{e}.{traceback.format_exc()}")
    async def yzj_fpy_chat(self,request: Request, msg: YZJRobotMsg,
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
            assistant_id = self.config_manager.get_assistant_id_by_yzj_token(yzj_token)
            if not assistant_id:
                logger.error(f"[yzj_token={yzj_token}]: 没有配置参数yzj_token的相关信息")
                result = {
                    "success": True,
                    "data": {"type": 2, "content": "没有配置知识库信息，请配置完再提问"}
                }
                return JSONResponse(content=result)
            assistant = self.get_assistant(assistant_id)

            # msg.content包含sync gpt(仍保留)，则同步语雀文档到gpt assistant
            if "sync gpt" in msg.content.lower():
                asst_type, llm_type = self.config_manager.get_asst_info_by_asst_id(assistant_id)
                sync_id = ASSISTANT_CONFIG[asst_type]['sync_flow_config']['id']
                task.add_task(self.yzjhandler.sync_gpt_assistant_on_yzj,
                              self.sync_manager.sync_dict[sync_id],
                              yzj_token, assistant, msg)
            else:
                task.add_task(self.yzjhandler.chat_doc, assistant, yzj_token, msg, self.database)
            result = {
                "success": True,
                "data": {"type": 2, "content": "请稍等..."}
            }
        except Exception as e:
            logger.error(f"[yzj_token={yzj_token}]: 出现错误:{e}.{traceback.format_exc()}")
            result = {
                "success": True,
                "data": {"type": 2, "content": "抱歉，目前存在问题，请稍后再试"}
            }
        return JSONResponse(content=result)

    async def force_sync(self, task: BackgroundTasks, assistant_id: str = Query(...)) -> JSONResponse:
        try:
            if assistant_id not in self.config_manager.get_all_asst_id() or not assistant_id:
                logger.error(f"不存在assistant_id '{assistant_id}'，请重新输入")
                result = {"success": False, "description": f"不存在assistant_id '{assistant_id}'，请重新输入"}
                return JSONResponse(content=result)
            assistant = self.get_assistant(assistant_id)
            asst_type, _ = self.config_manager.get_asst_info_by_asst_id(assistant_id)
            sync_id = ASSISTANT_CONFIG[asst_type]['sync_flow_config']['id']

            if assistant.asst_type == ASSTType.NATIVE_ASST:
                task.add_task(self.yzjhandler.manual_sync_gpt_assistant,
                              self.sync_manager.sync_dict[sync_id], assistant)
                result = {"success": True, "description": "正在同步中"}
            else:
                result = {"success": False, "description": f"未知助手类型 '{assistant.asst_type}'，同步助手失败"}
                logger.error(f"[asst_id={assistant_id}]：未知助手类型 '{assistant.asst_type}'，同步助手失败：{e}")
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
            assistant = self.get_assistant(assistant_id)
            asst_type, _ = self.config_manager.get_asst_info_by_asst_id(assistant_id)
            sync_id = ASSISTANT_CONFIG[asst_type]['sync_flow_config']['id']
            if asst_type == ASSTType.NATIVE_ASST:
                result = await asyncio.get_running_loop().run_in_executor(
                    None, self.yzjhandler.manual_sync_gpt_assistant, self.sync_manager.sync_dict[sync_id], assistant
                )
            else:
                logger.error(f"[asst_id={assistant_id}]：未知助手类型 '{asst_type}'，同步助手失败：{e}")
        except Exception as e:
            logger.error(f"[asst_id={assistant_id}]：同步助手失败：{e}")

    async def scheduler_tasks(self):
        logger.info("开始执行定时任务")
        # 定时同步任务
        tasks = []
        semaphore = asyncio.Semaphore(10)   # 设置并发执行的任务数量
        asst_ids = self.config_manager.get_all_asst_id()
        for assistant_id in asst_ids:
            if not assistant_id:
                logger.warning(f"不存在assistant_id '{assistant_id}'")
            else:
                async with semaphore:
                    task = asyncio.create_task(self.async_manual_sync(assistant_id))
                    tasks.append(task)
        # 等待所有后台任务完成
        await asyncio.gather(*tasks, return_exceptions=True)
        # 更新每个assistant的thread_map
        for assistant_id in asst_ids:
            asst = self.get_assistant(assistant_id)
            if asst is not None:
                asst.del_all_threads()
        logger.info("定时任务结束")

    async def update_to_yuque(self):
        """
        将前一天的所有数据更新到语雀文档中
        :return:
        """
        # 需要更新的url和表头
        yuque_url = "https://jdpiaozone.yuque.com/api/v2/repos/nbklz3/kro38t/docs/wthbafwdgo5zw783"
        yuque_headers = {
            "X-Auth-Token": YUQUE_CONFIG["yuque_auth_token"],
            "User-Agent": YUQUE_CONFIG["yuque_request_agent"]
                    }
        # 获取url现有数据
        try:
            response = requests.get(yuque_url, headers=yuque_headers)
            response.raise_for_status()
            existing_content = response.json()['data']
            existing_body = existing_content['body']
            update_time = existing_content.get('updated_at')
            logger.info(f"获取url现有数据成功，上次更新时间{update_time}")
        except requests.exceptions.RequestException as e:
            logger.error(f"获取现有数据失败：{e}")

        # 从数据库获取前一天0点到今天0点的数据
        table_class = FAQ
        now = datetime.datetime.now()
        yesterday = datetime.datetime.combine(now.date() - datetime.timedelta(days=1), datetime.time(0, 0))
        today = datetime.datetime.combine(now.date(), datetime.time(0, 0))
        filter_cond = and_(table_class.entry_time >= yesterday, table_class.entry_time <= today)
        extract_data = self.database.complex_query_data(table_class, filter_cond)
        # 列表储存得到的数据
        results = []
        for result in extract_data:
            res = {'id': result.id, 'topic_name': result.topic_name, 'question': result.question,
                   'answer': result.answer, 'has_answer': result.has_answer, 'asker': result.asker,
                   'entry_time': result.entry_time}
            results.append(res)
        logger.info(f"成功从数据库获取记录")

        #设定表头和新加的数据格式
        header = '| 序号 | 产品线 | 问题来源编号 | 问题模块 | 问题等级 | 问题描述 | GPT参考答案 | 知识库是否存在答案 | 最终回复答案 | 提问人 | 解答人 | 录入时间 |\n '
        header += '|---|---|---|---|---|---|---|---|---|---|---|---|\n'
        new_content = ''
        for item in results:
            format_ans = item['answer'].replace('\n', '<br />')
            row = f"| {item['id']} | {item['topic_name']} | <br /> | <br /> | <br /> | {item['question']} | {format_ans} | {item['has_answer']} | <br /> | {item['asker']} | <br /> | {item['entry_time']} |\n"
            new_content += row
        # 如果现有body不为空，加上新的数据，否则设定表头内容
        if existing_body.strip():
            update_content_body = existing_body + new_content
        else:
            update_content_body = header + new_content
        #更新的内容
        update_content = {
            'title': 'FAQ信息',
            'format': 'markdown',
            'body': update_content_body,
            'public': 2
        }
        # 发送 PUT 请求更新数据
        try:
            response = requests.put(yuque_url, headers=yuque_headers, json=update_content)
            response.raise_for_status()
            logger.info("数据更新成功")
        except requests.exceptions.RequestException as e:
            logger.error(f"数据更新失败：{e}")


    async def startup_tasks(self):
        """
        初始化定时任务
        """
        self.scheduler = AsyncIOScheduler()
        self.scheduler.add_job(self.scheduler_tasks, 'cron', day_of_week='sat', hour=2)
        self.scheduler.add_job(self.update_to_yuque, 'cron', day_of_week='*', hour=2)
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
            result = {"success": True, "description": "正在更新配置"}
        except Exception as e:
            result = {"success": False, "description": str(e)}
            logger.error(f"配置更新失败：{e}.{traceback.format_exc()}")
        return JSONResponse(content=result)
    async def get_config(self):
        try:
            result = {"success": True, "description": "操作成功",
                      "data": self.config_manager.index_data}
        except Exception as e:
            result = {"success": False, "description": str(e)}
            logger.error(f"获取配置失败：{e}.{traceback.format_exc()}")
        return JSONResponse(content=result)
    async def empty_files(self, assistant_id: str = Query(...)):
        """
        清空assistant的文件
        :return:
        """
        try:
            assistant = self.get_assistant(assistant_id)
            is_success = assistant.empty_files()
            result = {"success": is_success, "description": f"清空{'成功' if is_success else '失败'}"}
        except Exception as e:
            result = {"success": False, "description": str(e)}
            logger.error(f"清空文件失败：{e}.{traceback.format_exc()}")
        return JSONResponse(content=result)





if __name__ == "__main__":
    import uvicorn

    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["formatters"]["access"]["fmt"] = "[%(asctime)s %(filename)s:%(lineno)d] %(levelname)s: %(message)s"
    log_config["formatters"]["default"]["fmt"] = "[%(asctime)s %(filename)s:%(lineno)d] %(levelname)s: %(message)s"

    app = App()
    uvicorn.run(app, host="0.0.0.0", port=9999, log_config=log_config)
