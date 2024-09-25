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
import datetime
from pydantic import BaseModel
from src.utils.logger import logger
from src.utils.constants import QSource
from src.utils.database import QARecord
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
    def __init__(self, yunzhijia_config, auto_entry_config, config_manager):
        self.yunzhijia_notify_url = yunzhijia_config["notify_url"]
        self.max_img_num_in_card_notice = yunzhijia_config["max_img_num_in_card_notice"]
        self.card_notice_template_id = yunzhijia_config["card_notice_template_id"]
        self.auto_entry_config = auto_entry_config
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
            qa_assistant.save_qa_to_database(session_id=session_id,
                                              topic_name=topic_name,
                                              question=msg.content,
                                              answer=output,
                                              has_answer=has_answer,
                                              asker=msg.operatorName,
                                              source=QSource.YUNZHIJIA.value)

    def notice_yzj_group(self, yzj_token, content):
        start_data = {"content": content}
        requests.post(self.yunzhijia_notify_url.format(yzj_token), json=start_data)

    def auto_entry_qa(self):
        """
        将前一天的所有数据更新到语雀文档中
        :return:
        """
        # 获取url现有数据
        try:
            response = requests.get(self.auto_entry_config["url"], headers=self.auto_entry_config["headers"])
            response.raise_for_status()
            existing_data = response.json().get('data', {})
            existing_body = existing_data.get('body', '')
            format_body = existing_body.replace('<br />', '<br>').replace('\n', '<br>') #修改单元格内换行符
            existing_content = format_body.replace('|<br>', '|\n').rstrip('<br>') #替换表格结尾
            update_time = existing_data.get('updated_at')
            logger.info(f"获取url现有数据成功，上次更新时间 '{update_time}'")
        except requests.exceptions.RequestException as e:
            logger.error(f"获取现有数据失败：{e}")
            return

        # 从数据库获取前一天0点到今天0点的数据
        table_class = QARecord
        now = datetime.datetime.now()
        yesterday = datetime.datetime.combine(now.date() - datetime.timedelta(days=1), datetime.time(0, 0))
        today = datetime.datetime.combine(now.date(), datetime.time(0, 0))
        filter_cond = and_(table_class.created_at >= yesterday, table_class.created_at <= today,
                           table_class.source == QSource.YUNZHIJIA.value)
        extract_data = self.database.complex_query_data(table_class, filter_cond)
        # 列表储存得到的数据
        results = [
            {
                'id': result.id,
                'topic_name': result.topic_name,
                'question': result.question,
                'answer': result.answer,
                'has_answer': result.has_answer,
                'asker': result.asker,
                'created_at': result.created_at
            }
            for result in extract_data
        ]
        logger.info(f"成功从数据库获取 yunzhijia 记录")

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
            row = f"| {item['id']} | {f_topic_name} |   |   |   | {f_question} | {f_answer} | {item['has_answer']} |   | {f_asker} |   | {item['created_at']} |\n"
            new_content += row
        # 如果现有body不为空，加上新的数据，否则设定表头内容
        if existing_content.strip():
            update_content_body = existing_content + new_content
        else:
            update_content_body = header + new_content

        #更新的内容
        update_content = {
            'title': 'QA信息',
            'format': 'markdown',
            'body': update_content_body,
            'public': 2
        }
        # 发送 PUT 请求更新数据
        try:
            response = requests.put(self.auto_entry_config["url"], headers=self.auto_entry_config["headers"], json=update_content)
            response.raise_for_status()
            logger.info("数据更新成功")
        except requests.exceptions.RequestException as e:
            logger.error(f"数据更新失败：{e}")


