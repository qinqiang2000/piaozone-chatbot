import time

import traceback
import openai
from openai import AzureOpenAI
from openai.types.beta.threads import Run

from src.utils.logger import logger

# Assistant类，用于处理openai的对话请求
class Assistant:
    def __init__(self, assistant_id: str, api_key: str = None,
                 azure_endpoint: str = None, api_version: str = None,
                 deployment_name: str = None):
        self.client = AzureOpenAI(api_key=api_key, api_version=api_version, azure_endpoint=azure_endpoint)
        self.deployment_name = deployment_name
        self.assistant_id = assistant_id
        self.thread_map = {}  # 英文指定id创建thread，所以需要一个map来存储session id(robot id + "~" + operatorOpenId)和thread_id的映射关系
    def create_assistant(self, name: str, instructions: str = None):
        assistant = self.client.beta.assistants.create(
            name=name,
            instructions=instructions,
            model=self.deployment_name
        )
        self.assistant_id = assistant.id
        return assistant.id
    def check_asst_file(self) -> bool:
        """
        检查assistant是否有文件
        :return:
        """
        assistant_files = self.list_files()
        if assistant_files.data:
            return True
        return False

    def chat(self, session_id: str, content: str) -> str:
        """
        用户发送消息，调用openai的接口，返回回复
        :param session_id: 由{app_type}~{robot_id}~{operatorOpenId}组成
        :param content:
        :return:
        """
        # 如果session_id不存在，创建一个新的thread;
        if session_id not in self.thread_map:
            thread = self.client.beta.threads.create()
            self.thread_map[session_id] = thread.id
        # 1. 获取thread_id
        thread_id = self.thread_map.get(session_id)

        # 2.构造openai的message
        self.client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=content
        )
        # 3.运行assistant
        run = self.client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=self.assistant_id
        )
        # 4.等待assistant运行完成
        # 运行状态：queued, in_progress, requires_action, cancelling, cancelled, failed, completed, or expired
        run = self.__wait_on_run(run=run, session_id=session_id)

        if run.status == "completed":
            messages = self.client.beta.threads.messages.list(thread_id=thread_id, limit=1)
            logger.debug(f"[{session_id}]: {messages.data[0].content[0]}")
            message_content = messages.data[0].content[0].text
            if message_content.annotations:
                message_content = self.process_annotation(message_content)
            return message_content.value
        logger.debug(f"[{session_id}]: {run.status}")
        return None

    def __wait_on_run(self, run: Run, session_id: str) -> Run:
        """
        检索assistant运行状态，直到运行完成
        :param run:
        :param session_id: 由{app_type}~{robot_id}~{operatorOpenId}组成
        :return:
        """

        thread_id = self.thread_map.get(session_id)
        if not thread_id:
            return None
        num_retries = 0
        while True:
            time.sleep(1)
            run = self.client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
            logger.debug(f"[session_id: {session_id}, thread_id: {thread_id}]: {run.status}")
            if run.status not in ["queued", "in_progress"]:
                break
            num_retries += 1
            if num_retries > 59:
                break
        return run

    def process_annotation(self, message_content):
        annotations = message_content.annotations
        citations = []
        try:
            process_content = message_content.value
            # Iterate over the annotations and add footnotes
            for index, annotation in enumerate(annotations):
                # Replace the text with a footnote
                process_content = process_content.replace(annotation.text, f' [{index}]')

                # Gather citations based on annotation attributes
                if (file_citation := getattr(annotation, 'file_citation', None)):
                    cited_file = self.client.files.retrieve(file_citation.file_id)
                    citations.append(f'[{index}] {file_citation.quote}')
                elif (file_path := getattr(annotation, 'file_path', None)):
                    cited_file = self.client.files.retrieve(file_path.file_id)
                    citations.append(f'[{index}] 来自 {cited_file.filename}')
            # Add footnotes to the end of the message before displaying to user
            process_content += '\n' + '\n'.join(citations)
            message_content.value = process_content
        except:
            logger.error(f"assistant 返回内容存在问题：{message_content}\n {traceback.format_exc()}")
        return message_content

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
            logger.info(f"清空assistant文件：{deleted_id}")
            return len(deleted_id)
        except Exception as e:
            logger.error(f"清空assistant文件失败：{e}")
            return -1

    def update_asst_files(self, file_paths):
        """
        更新assistant的文件
        :param file_paths: 文件路径列表
        :return: 上传成功的文件列表
        """
        assistant_files = []
        for file_path in file_paths:
            assistant_file = self.create_file(file_path)
            assistant_files.append(assistant_file)
        assistant = self.client.beta.assistants.update(
            assistant_id=self.assistant_id,
            file_ids=[file.id for file in assistant_files]
        )
        return assistant_files

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
            # assistant = self.client.beta.assistants.update(
            #     assistant_id="asst_ ........ Dmo3S",
            #     file_ids=[file_1.id, file_2.id, file_3.id]
            # )
            return assistant_file

    def del_file(self, file_id):
        try:
            deleted_assistant_file = self.client.beta.assistants.files.delete(
                assistant_id=self.assistant_id,
                file_id=file_id
            )
            file = self.client.files.delete(file_id)
            logger.info(f"删除上一次的文件：{deleted_assistant_file} {file}")
            return deleted_assistant_file
        except openai.NotFoundError as e:
            logger.error(f"不存在：{e}")

    def del_assistant(self):
        assistant_files = self.client.beta.assistants.files.list(
            assistant_id=self.assistant_id,
            limit=100
        )
        for file in assistant_files.data:
            self.client.beta.assistants.files.delete(assistant_id=self.assistant_id, file_id=file.id)
            self.client.files.delete(file.id)
        self.client.beta.assistants.delete(self.assistant_id)

    def del_all_threads(self):
        for session_id in self.thread_map.keys():
            thread_id = self.thread_map.get(session_id)
            self.client.beta.threads.delete(thread_id)
        self.thread_map = {}

    def del_thread(self, session_id: str):
        if session_id in self.thread_map:
            thread_id = self.thread_map.pop(session_id)
            self.client.beta.threads.delete(thread_id)



