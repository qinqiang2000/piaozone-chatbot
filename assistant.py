import logging

import openai
from openai import OpenAI

from common_utils import *


# Assistant类，用于处理openai的对话请求
class Assistant:
    def __init__(self, assistant_id, api_key=None, base_url=None, ):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.assistant_id = assistant_id
        self.run = None
        self.thread_map = {}  # 英文指定id创建thread，所以需要一个map来存储session id(robot id + "~" + operatorOpenId)和thread_id的映射关系

    def chat(self, session_id, content):
        """
        :param session_id: 由{robot_id}~{operatorOpenId}组成
        :param content:
        :return:
        """
        # 如果session_id不存在，创建一个新的thread;
        if session_id not in self.thread_map:
            thread = self.client.beta.threads.create()
            self.thread_map[session_id] = thread.id

        thread_id = self.thread_map.get(session_id)

        self.client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=content
        )

        self.run = self.client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=self.assistant_id
        )

    def get_answer(self, session_id):
        """
        :param session_id:由{robot_id}~{operatorOpenId}组成
        :return:
        """
        thread_id = self.thread_map.get(session_id)
        if not thread_id:
            return None

        run = self.client.beta.threads.runs.retrieve(
            thread_id=thread_id,
            run_id=self.run.id
        )

        if run.status != "completed":
            logging.debug(f"[{session_id}]: {run.status}")
            return None

        messages = self.client.beta.threads.messages.list(thread_id=thread_id, limit=1)
        logging.debug(f"[{session_id}]: {messages.data[0].content[0]}")
        return messages.data[0].content[0].text

    def list_files(self):
        assistant_files = self.client.beta.assistants.files.list(
            assistant_id=self.assistant_id,
            limit=100
        )
        return assistant_files

    def empty_files(self):
        """
        :param 清空assistant的文件
        :return: 清空的文件数量；-1 表示清空失败
        """
        try:
            assistant_files = self.list_files()
            for file in assistant_files.data:
                self.client.beta.assistants.files.delete(
                    assistant_id=self.assistant_id,
                    file_id=file.id
                )
                self.client.files.delete(file.id)

            deleted_id = list(map(lambda x: x['id'], assistant_files.data))
            logging.info(f"清空assistant文件：{deleted_id}")
            return len(deleted_id)
        except Exception as e:
            logging.error(f"清空assistant文件失败：{e}")
            return -1

    def create_file(self, file_path):
        # 上传新文件
        with open(file_path, "rb") as f:
            file = self.client.files.create(
                file=f,
                purpose='assistants'
            )
            # 加载到新文件到assistant
            assistant_file = self.client.beta.assistants.files.create(
                assistant_id=self.assistant_id,
                file_id=file.id
            )
            return assistant_file

    def del_file(self, file_id):
        try:
            deleted_assistant_file = self.client.beta.assistants.files.delete(
                assistant_id=self.assistant_id,
                file_id=file_id
            )
            file = self.client.files.delete(file_id)
            logging.info(f"删除上一次的文件：{deleted_assistant_file} {file}")
            return deleted_assistant_file
        except openai.NotFoundError as e:
            logging.error(f"不存在：{e}")
