#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
import asyncio
import os
from typing import Any,Optional
import sys
import importlib
import traceback
from pydantic import BaseModel,ValidationError
from fastapi.exceptions import RequestValidationError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from concurrent.futures import ThreadPoolExecutor
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
from src.handlers.yunzhijia_handler import YZJHandler, YZJRobotMsg
from src.handlers.zhichi_handler import ZhiChiHandler, ZCRobotMsg
from src.qa_assistant.base_assistant import ASSTType
from src.utils.database import SQLDatabase, FAQ
import datetime
from sqlalchemy import and_
import requests

class YQMsg(BaseModel):
    data: Optional[dict] = None

executor = ThreadPoolExecutor(50)

class App(FastAPI):
    """
    知识库问答助手应用
    """
    def __init__(self, **extra: Any):
        super().__init__(**extra)
        # 1. 初始化 config
        self.config_manager = ConfigManager(
            yuque_config=YUQUE_CONFIG,
            config_info=CONFIG_INFO)

        # 2. 初始化语雀到assistant 或者其他的同步组件
        yuque_repos = self.config_manager.get_all_yq_repo()
        self.sync_manager = SyncManager(yuque_config=YUQUE_CONFIG,yuque_repos=yuque_repos,sync_configs=SYNC_CONFIGS)

        # 3. 初始化数据库
        self.database = SQLDatabase(**DB_CONFIG)
        # self.database.create_table(table_class=FAQ) #建表储存问答信息


        # 4. 初始化gpt assistants
        self.init_asst()

        # 5. 初始化云之家处理器和智齿处理器
        self.yzjhandler = YZJHandler(yunzhijia_config=YUNZHIJIA_CONFIG,
                                     config_manager=self.config_manager)
        self.zhichihandler = ZhiChiHandler(config_manager=self.config_manager)

        # 6、添加定时任务,每周6 2点触发定时同步任务，每天1点触发定时自动录入任务
        self.add_event_handler("startup", self.startup_tasks)
        self.add_event_handler("shutdown", self.shutdown_tasks)

        # 7、添加 api_route
        self.add_api_route("/yzj/chat", self.yzj_chat, methods=["POST"])
        self.add_api_route("/zhichi/chat", self.zhichi_chat, methods=["POST"])
        # self.add_api_route("/yuque/webhook", self.yuque_sync_info_update, methods=["POST"])
        self.add_api_route("/sync", self.force_sync, methods=["POST"])
        self.add_api_route("/empty_file", self.empty_files, methods=["POST"])
        self.add_api_route("/del_session", self.del_session, methods=["POST"])
        self.add_api_route("/get_thread", self.get_thread_id, methods=["GET"])
        self.add_api_route("/yuque/config_update", self.yuque_update_config, methods=["POST"])
        self.add_api_route("/update_config", self.force_update_config, methods=["POST"]) # 强制更新配置
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
                logger.error(f"[asst_id={asst_id}]: 初始化助手失败：{e}.{traceback.format_exc()}")
    def get_assistant(self,assistant_id):
        if assistant_id in self.assistants:
            return self.assistants[assistant_id]
        assistant_ins = self.get_new_assistant(assistant_id, ASSISTANT_CONFIG, LLM_CONFIGS)
        if assistant_ins is not None:
            self.assistants[assistant_id] = assistant_ins
        return assistant_ins
    def get_new_assistant(self, assistant_id, asst_configs, llm_configs):
        if assistant_id not in self.config_manager.get_all_asst_id():
            logger.error(f"[asst_id={assistant_id}]: 助手id不存在")
            return None
        asst_type, llm_type = self.config_manager.get_asst_info_by_asst_id(assistant_id)
        yq_info = self.config_manager.get_yq_info_by_asst_id(assistant_id)
        yq_info_dict = {}
        for repo, toc_title in yq_info:
            if repo not in yq_info_dict:
                yq_info_dict[repo] = []
            yq_info_dict[repo].append(toc_title)

        topic = "_".join([f"{repo}_{'-'.join(toc_titles)}" for repo, toc_titles in yq_info_dict.items()])
        if asst_type not in asst_configs:
            logger.error(f"[asst_id={assistant_id}]: 不合法的助手类型: {asst_type}")
            return None
        llm_module = importlib.import_module(f"src.qa_assistant.{asst_type}")
        asst_config = asst_configs[asst_type].copy()
        asst_config["llm_option"] = llm_type
        assistant_ins = llm_module.Assistant(assistant_id=assistant_id,
                                             assistant_config=asst_config,
                                             llm_configs=llm_configs,
                                             topic=topic,
                                             database=self.database)
        if not assistant_ins.check_asst_file():

            logger.info(f"[asst_id={assistant_id}]: 助手不存在文件，开始同步专题库 '{','.join([x[1] for x in yq_info])}' 的文件")
            sync_id = asst_config['sync_flow_config']['id']
            ret = self.sync_manager.sync_dict[sync_id].sync_yq_doc_to_dest(yq_info,
                                                                           assistant_ins)
            # 如果同步失败：
            if not ret:
                return None
        return assistant_ins

    async def yzj_chat(self,request: Request, msg: YZJRobotMsg,
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
            logger.info(f"[yzj_token={yzj_token}]输入消息: {msg}")
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
            is_auto_entry = self.config_manager.get_auto_entry_info_by_yzj_token(yzj_token)

            task.add_task(self.yzjhandler.chat_doc, assistant, yzj_token, msg, is_auto_entry)
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

    async def validation_exception_handler(self, request: Request, exc: RequestValidationError):
        """处理请求验证错误"""
        # 尝试获取原始请求体
        try:
            body = await request.json()
        except:
            body = {}

        # 尝试从请求体中获取 cid 和 msgid
        cid = body.get('cid', '')
        msgid = body.get('msgid', '')

        result = {
            "ret_code": "000003",
            "ret_msg": "输入验证错误",
            "item": {
                "cid": cid,
                "msgid": msgid,
                "answer_txt": str(exc),
                "answer_txt_type": "0",
                "answer_type": "3"
            }
        }
        return JSONResponse(content=result, status_code=422)
    async def zhichi_chat(self,msg: ZCRobotMsg) -> JSONResponse:
        """
        智齿对话接口
        :param msg: 智齿机器人消息
        :return: JSON响应
        """
        try:
            logger.info(f"[zhichi_session_id={msg.cid}]输入消息: {msg}")
            # 、获取assistant，智齿只需要配置一个assistant，所以直接取第一个即可
            zhichi_asst_info = list(self.config_manager.index_data.get("zhichi_config",{}))
            assistant_id = zhichi_asst_info[0] if len(zhichi_asst_info) > 0 else None
            if not assistant_id:
                logger.error(f"没有配置有效的助手id,请配置完后重试")
                result = {
                    "ret_code": "000001",
                    "ret_msg": "没有配置助手id，请配置完后重试",
                    "item": {"cid": msg.cid,
                             "msgid": msg.msgid,
                             "answer_txt": "没有配置助手id，请配置完后重试",
                             "answer_txt_type": "0",
                             "answer_type": "3"}
                }
                return JSONResponse(content=result)
            assistant = self.get_assistant(assistant_id)
            is_auto_entry = self.config_manager.index_data["zhichi_config"][assistant_id].get("is_auto_entry", False)
            loop = asyncio.get_event_loop()
            answer, has_answer = await loop.run_in_executor(executor, self.zhichihandler.chat_doc, assistant, msg, is_auto_entry)
            result = {
                "ret_code": "000000",
                "ret_msg": "操作成功",
                "item": {"cid": msg.cid,
                         "msgid": msg.msgid,
                         "answer_txt": answer,
                         "answer_txt_type": "0",
                         "answer_type": "1" if has_answer else "3"}
            }
            return JSONResponse(content=result)
        except Exception as e:
            logger.error(f"[zhichi_session_id={msg.cid}]: 出现错误:{e}.{traceback.format_exc()}")
            result = {
                    "ret_code": "000002",
                    "ret_msg": "出现未知错误",
                    "item": {"cid": msg.cid,
                             "msgid": msg.msgid,
                             "answer_txt": "",
                             "answer_txt_type": "0",
                             "answer_type": "3"}
                }
            return JSONResponse(content=result)

    def sync_assistant(self, assistant_id: str):
        assistant = self.get_assistant(assistant_id)
        asst_type, _ = self.config_manager.get_asst_info_by_asst_id(assistant_id)
        yq_info = self.config_manager.get_yq_info_by_asst_id(assistant_id)
        yzj_tokens = self.config_manager.get_yzj_token_by_asst_id(assistant_id)
        sync_id = ASSISTANT_CONFIG[asst_type]['sync_flow_config']['id']
        logger.info(f"语雀知识库'{','.join([x[1] for x in yq_info])}' 需要同步至assistant: '{assistant_id}'")
        # 通知云之家需要开始同步
        for yzj_token in yzj_tokens:
            self.yzjhandler.notice_yzj_group(yzj_token=yzj_token, content="开始同步新文档至Assistant,如果有什么问题请同步结束后再提问。")
        # 同步知识库数据到assistant
        ret = self.sync_manager.sync_dict[sync_id].sync_yq_doc_to_dest(yq_info, assistant)
        success = "成功"
        if ret:
            logger.info(f"同步知识库'{','.join([x[1] for x in yq_info])}'数据到 assistant成功: {assistant_id}")
        else:
            success = "失败"
        # 通知云之家同步结束
        for yzj_token in yzj_tokens:
            self.yzjhandler.notice_yzj_group(yzj_token=yzj_token, content=f"同步最新文档至Assistant{success}。")
        return success

    async def force_sync(self, task: BackgroundTasks, assistant_id: str = Query(...)) -> JSONResponse:
        try:
            if assistant_id not in self.config_manager.get_all_asst_id() or not assistant_id:
                logger.error(f"不存在assistant_id '{assistant_id}'，请重新输入")
                result = {"success": False, "description": f"不存在assistant_id '{assistant_id}'，请重新输入"}
                return JSONResponse(content=result)
            task.add_task(self.sync_assistant,assistant_id)
            result = {"success": True, "description": "正在同步中"}
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
                None, self.sync_assistant, assistant_id
            )
        except Exception as e:
            logger.error(f"[asst_id={assistant_id}]：同步助手失败：{e}")

    async def scheduler_sync_tasks(self):
        logger.info("开始执行定时同步任务")
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
        logger.info("定时同步任务结束")

    def auto_entry_faq(self):
        """
        将前一天的所有数据更新到语雀文档中
        :return:
        """
        # 需要更新的url和表头
        yuque_url = f"{YUQUE_CONFIG['yuque_base_url']}/repos/{YUQUE_CONFIG['yuque_namespace']}/{AUTO_ENTRY_CONFIG['repo']}/docs/{AUTO_ENTRY_CONFIG['slug']}"
        yuque_headers = {
            "X-Auth-Token": YUQUE_CONFIG["yuque_auth_token"],
            "User-Agent": YUQUE_CONFIG["yuque_request_agent"]
                    }
        # 获取url现有数据
        try:
            response = requests.get(yuque_url, headers=yuque_headers)
            response.raise_for_status()
            existing_data = response.json()['data']
            existing_body = existing_data['body']
            format_body = existing_body.replace('<br />', '<br>').replace('\n', '<br>') #修改单元格内换行符
            existing_content = format_body.replace('|<br><br>', '|\n').replace('|<br>', '|\n') #替换表格结尾
            update_time = existing_data.get('updated_at')
            logger.info(f"获取url现有数据成功，上次更新时间{update_time}")
            #logger.info(f"url现有数据：{existing_content}")
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
            #统一格式，替换换行符
            f_topic_name = item['topic_name'].replace('\n', '<br>')
            f_question = item['question'].replace('\n', '<br>')
            f_answer = item['answer'].replace('\n', '<br>')
            f_asker = item['asker'].replace('\n', '<br>')
            row = f"| {item['id']} | {f_topic_name} |   |   |   | {f_question} | {f_answer} | {item['has_answer']} |   | {f_asker} |   | {item['entry_time']} |\n"
            new_content += row
        # 如果现有body不为空，加上新的数据，否则设定表头内容
        if existing_content.strip():
            update_content_body = existing_content + new_content
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

    async def scheduler_auto_entry_tasks(self):
        logger.info("开始执行定时录入任务")
        await asyncio.get_event_loop().run_in_executor(executor, self.auto_entry_faq)
        logger.info("定时录入任务结束")


    async def startup_tasks(self):
        """
        初始化定时任务
        """
        self.scheduler = AsyncIOScheduler()
        self.scheduler.add_job(self.scheduler_sync_tasks, 'cron', day_of_week='sat', hour=2)
        self.scheduler.add_job(self.scheduler_auto_entry_tasks, 'cron', day_of_week='*', hour=1)
        self.scheduler.start()
        logger.info("设置定时任务成功")
    async def shutdown_tasks(self):
        """
        在结束时同步并关闭定时器
        """
        self.scheduler.shutdown()
        logger.debug("关闭程序")

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
            logger.info("配置更新成功")
        except Exception as e:
            logger.error(f"配置更新失败：{e}.{traceback.format_exc()}")

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
                if (repo,doc_slug) in self.config_manager.config_info_tuple:
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
    def get_config(self):
        try:
            result = {"success": True, "description": "操作成功",
                      "data": self.config_manager.index_data}
        except Exception as e:
            result = {"success": False, "description": str(e)}
            logger.error(f"获取配置失败：{e}.{traceback.format_exc()}")
        return JSONResponse(content=result)
    def empty_files(self, assistant_id: str = Query(...)):
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
    def del_session(self, assistant_id: str = Query(...), session_id: str = Query(...)):
        """
        清空assistant的文件
        :return:
        """
        try:
            assistant = self.get_assistant(assistant_id)
            assistant.del_thread(session_id)
            result = {"success": True, "description": "成功删除"}
        except Exception as e:
            result = {"success": False, "description": str(e)}
            logger.error(f"删除thread失败：{e}.{traceback.format_exc()}")
        return JSONResponse(content=result)
    def get_thread_id(self, assistant_id: str = Query(...), session_id: str = Query(...)):
        try:
            assistant = self.get_assistant(assistant_id)
            result = {"success": True, "description": "操作成功",
                      "data": assistant.get_thread_id(session_id)}
        except Exception as e:
            result = {"success": False, "description": str(e)}
            logger.error(f"获取助手thread id失败：{e}.{traceback.format_exc()}")
        return JSONResponse(content=result)





if __name__ == "__main__":
    import uvicorn

    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["formatters"]["access"]["fmt"] = "[%(asctime)s %(filename)s:%(lineno)d] %(levelname)s: %(message)s"
    log_config["formatters"]["default"]["fmt"] = "[%(asctime)s %(filename)s:%(lineno)d] %(levelname)s: %(message)s"

    app = App()
    uvicorn.run(app, host="0.0.0.0", port=9999, log_config=log_config)
