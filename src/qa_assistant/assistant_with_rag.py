import time
import json

import traceback
from openai.types.beta.threads import Run

from src.tools.rag.simple_rag import SimpleRAGTool
from src.qa_assistant.base_assistant import BaseAssistant, ASSTType
from src.tools import ToolType
from src.tools.rag.base_rag import RAGType
from src.utils.logger import logger

# Assistant类，用于处理openai的对话请求
class Assistant(BaseAssistant):
    def __init__(self, assistant_id: str, assistant_config: dict, topic: str):
        super().__init__(assistant_id, assistant_config)
        self.asst_type = ASSTType.ASST_WITH_SIMPLE_RAG
        self.setup_tools(tool_list=assistant_config["tool_config"], topic=topic)
        self.thread_map = {}  # 英文指定id创建thread，所以需要一个map来存储session id(robot id + "~" + operatorOpenId)和thread_id的映射关系
    def setup_tools(self, tool_list, topic: str):
        self.tools = {}
        self.rag_names = []
        for tool in tool_list:
            if tool["tool_type"] == ToolType.RAG:
                if tool["tool_config"]["rag_option"] == RAGType.SIMPLE_RAG:
                    rag_tool = SimpleRAGTool(rag_config=tool["tool_config"], topic=topic)
                    self.tools[rag_tool.name] = rag_tool
                    self.rag_names.append(rag_tool.name)
    def check_asst_file(self) -> bool:
        """
        检查所有RAG工具是否有文件
        :return:
        """
        for rag_tool in self.rag_names:
            if not self.tools[rag_tool].doc_store.has_project():
                return False
        return True
    def create_assistant(self, name: str, instructions: str = None):
        assistant = self.client.beta.assistants.create(
            name=name,
            instructions=instructions,
            model=self.model_name,
            tools=[tool.tool_schema for tool in self.tools.values()]
        )
        self.assistant_id = assistant.id
        return assistant.id
    def get_message_memory(self, thread_id):
        """Get the memory of a thread"""
        messages = []
        for m in self.client.beta.threads.messages.list(thread_id=thread_id, order="asc"):
            messages.append({"role": m.role,"content": m.content[0].text.value})
        return messages

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
            return message_content.value
        logger.debug(f"[{session_id}]: {run.status}")
        if run.status == "failed":
            logger.error(f"[{session_id}]:状态：{run.status}. 明细:\n{run.last_error.message}")
        else:
            logger.error(f"[{session_id}]:状态：{run.status}.")
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
            if run.status == "requires_action":
                run = self.invoke_tools(
                    thread_id=thread_id,
                    run=run,
                )
            if run.status not in ["queued", "in_progress"]:
                break
            num_retries += 1
            if num_retries > 200:
                break
        return run
    def invoke_tools(self, thread_id: str, run: Run):
        """Invoke tools"""
        start_time = time.time()
        tool_calls = run.required_action.submit_tool_outputs.tool_calls
        tool_outputs = []
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            tool_call_id = tool_call.id
            try:
                tool_arguments = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError:
                pass

            tool_response = self.tools[tool_name](** tool_arguments)
            tool_outputs.append(
                {
                    "tool_call_id": tool_call_id,
                    "output": json.dumps(tool_response)
                }
            )
        end_time = time.time()
        if end_time - start_time < 1:
            time.sleep(2)
        run = self.client.beta.threads.runs.submit_tool_outputs(
            thread_id=thread_id,
            run_id=run.id,
            tool_outputs=tool_outputs
        )
        return run
    def update_asst_files(self, docs_chunks: list):
        is_success = True
        for tool in self.tools.values():
            if getattr(tool, "rag_type", None) == RAGType.SIMPLE_RAG:
                if not tool.doc_store.has_project():
                    is_one_success = tool.doc_store.init_doc_store(documents=docs_chunks)
                else:
                    is_one_success = tool.doc_store.partial_update_documents(documents=docs_chunks)
                logger.debug(f"同步数据到{doc_store.project_name}{'成功' if is_success else '失败'}。")
                if not is_one_success:
                    is_success = False
        return is_success
    def empty_files(self):
        is_success = True
        for tool in self.tools.values():
            if getattr(tool, "rag_type", None) == RAGType.SIMPLE_RAG:
                try:
                    tool.doc_store.delete_project()
                except:
                    is_success = False
        return is_success
    def del_assistant(self):
        try:
            self.client.beta.assistants.delete(self.assistant_id)
            logger.info(f"删除助手 {self.assistant_id} 成功")
            self.assistant_id = None
        except:
            logger.error(f"删除助手 {self.assistant_id} 失败")

    def del_all_threads(self):
        for session_id in self.thread_map.keys():
            thread_id = self.thread_map.get(session_id)
            self.client.beta.threads.delete(thread_id)
        self.thread_map = {}
    def del_thread(self, session_id: str):
        if session_id in self.thread_map:
            thread_id = self.thread_map.pop(session_id)
            self.client.beta.threads.delete(thread_id)
