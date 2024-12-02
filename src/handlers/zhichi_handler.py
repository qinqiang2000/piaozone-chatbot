"""
============================
# -*- coding: utf-8 -*-
# @Time    : 2024/1/16 15:29
# @Author  : LinLimin
# @Desc    : 用于处理云之家消息的handler
===========================
"""
import io
from typing import Optional,Dict,Any
from pydantic import BaseModel
from datetime import datetime, date
import pandas as pd
from fastapi import Request, Query, BackgroundTasks
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from src.utils.logger import logger
from src.utils.constants import QSource
from src.utils.database import QARecord


class ZCRobotMsg(BaseModel):
    cid: str
    msgid: str
    query_txt: str
    partnerid: str
    multi_params: Optional[Any] = None



class ZhiChiHandler:
    HANDLER_TYPE = "zhichi"
    templates = Jinja2Templates(directory="src/templates")
    def __init__(self, config_manager,database):
        self.config_manager = config_manager
        self.database = database
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
                topic_name = '/'.join([title for _, title in yq_info])
                qa_assistant.save_qa_to_database(session_id=msg.cid,
                                                 msg_id=msg.msgid,
                                                 topic_name=topic_name,
                                                 question=msg.query_txt,
                                                 answer=output,
                                                 has_answer=has_answer,
                                                 source=QSource.ZHICHI.value)
                if msg.cid and msg.msgid:
                    output = f"{output}\n\n点赞：{host}/like/{msg.cid}/{msg.msgid}\n点踩：{host}/dislike/{msg.cid}/{msg.msgid}"

        except:
            logger.error(f"[asst_id={qa_assistant.assistant_id};zhichi_session_id={session_id}]自动问答记录失败")
        return output, has_answer
    async def qa_query_page(self, request: Request):
        today = date.today().isoformat()
        return self.templates.TemplateResponse("qa_query.html", {
            "request": request,
            "today": today
        })

    def query_qa(self,
                  start_date: str = Query(None),
                  end_date: str = Query(None),
                  page: int = Query(1, ge=1),
                  per_page: int = Query(50, ge=1, le=100)):
        try:
            if not start_date:
                start_date = date.today().isoformat()
            if not end_date:
                end_date = date.today().isoformat()
            # 转换日期
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)

            # 查询数据
            with self.database.Session() as session:
                query = session.query(
                    QARecord.session_id, QARecord.msg_id, QARecord.question, QARecord.answer, QARecord.created_at
                ).filter(
                    QARecord.created_at >= start, QARecord.created_at <= end, QARecord.source == QSource.ZHICHI.value
                )
                # 获取总记录数
                total_count = query.count()

                # 分页
                qas = query.order_by(QARecord.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()

            result = [
                {
                    "session_id": qa.session_id,
                    "msg_id": qa.msg_id,
                    "question": qa.question,
                    "answer": qa.answer,
                    "created_at": qa.created_at.isoformat() if qa.created_at else None
                }
                for qa in qas
            ]
            logger.info(f"查询 zhichi 数据成功")
            return JSONResponse(content={
                "success": True,
                "data": result,
                "total": total_count,
                "page": page,
                "per_page": per_page,
                "total_pages": (total_count + per_page - 1) // per_page
            })
        except Exception as e:
            logger.error(f"查询QA时出错: {e}")
            return JSONResponse(content={"success": False, "message": "查询出错"}, status=500)

    def export_qa(self, start_date: str = Query(None), end_date: str = Query(None)):
        try:
            # 如果没有提供日期，使用当天日期
            if not start_date:
                start_date = date.today().isoformat()
            if not end_date:
                end_date = date.today().isoformat()

            # 转换日期
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)

            # 生成Excel文件
            excel_file = self._generate_excel(start, end)
            headers = {
                "Content-Disposition": f"attachment; filename=QA_{start.date()}_{end.date()}.xlsx".encode("utf-8").decode("latin1")}
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            logger.info(f"导出 zhichi 数据成功")

            return StreamingResponse(excel_file, media_type=media_type, headers=headers)

        except Exception as e:
            logger.error(f"导出QA时出错: {e}")
            return JSONResponse(content={"success": False, "message": "导出出错"}, status_code=500)

    def _generate_excel(self, start: datetime, end: datetime):
        try:
            with self.database.Session() as session:
                query = session.query(
                    QARecord.session_id, QARecord.msg_id, QARecord.question, QARecord.answer, QARecord.created_at
                ).filter(
                    QARecord.created_at >= start, QARecord.created_at <= end, QARecord.source == QSource.ZHICHI.value
                )
                qas = query.all()
            data = [
                {
                    "会话id": qa.session_id,
                    "消息id": qa.msg_id,
                    "问题": qa.question,
                    "回答": qa.answer,
                    "创建时间": qa.created_at.isoformat() if qa.created_at else None
                }
                for qa in qas
            ]

            df = pd.DataFrame(data)
            excel_file = io.BytesIO()
            with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='QA数据')

            excel_file.seek(0)
            return excel_file

        except Exception as e:
            logger.error(f"生成Excel文件时出错: {e}")
            raise



