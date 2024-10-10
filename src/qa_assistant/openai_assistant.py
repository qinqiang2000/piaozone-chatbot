import time

import traceback
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from openai import OpenAI, NotFoundError
from openai.types.beta.threads import Run

from src.qa_assistant.base_assistant import BaseAssistant, ASSTType
from src.utils.logger import logger
from src.utils.data_process import process_topic_name
from src.utils.database import SQLDatabase, FileAndUrlTable, QARecord

# Assistant类，用于处理openai的对话请求
class Assistant(BaseAssistant):
    def __init__(self, assistant_id: str, assistant_config: dict, llm_configs: dict, topic: str, database: SQLDatabase):
        super().__init__(assistant_id, assistant_config, llm_configs)
        self.topic = process_topic_name(topic)
        self.asst_type = ASSTType.OPENAI_ASSISTANT
        self.database = database
        self.table_class = FileAndUrlTable
        # self.database.create_table(self.table_class)
        self.thread_map = {}
        # 英文指定id创建thread，所以需要一个map来存储session id和thread_id的映射关系， TODO:后续换成 redis缓存或者MYSQL

    def get_vector_store_ids(self):
        vector_store = []
        try:
            my_assistant = self.client.beta.assistants.retrieve(self.assistant_id)
            file_search = my_assistant.tool_resources.file_search
            if file_search is None:
                logger.error(f"[asst_id={self.assistant_id}]：assistant没有启用file_search工具")
                return vector_store
            vector_store = my_assistant.tool_resources.file_search.vector_store_ids
        except Exception as e:
            logger.error(f"[asst_id={self.assistant_id}]：获取vector store失败：{e}")
        return vector_store
    def create_assistant(self, name: str, instructions: str = None, model_name="gpt-4-1106-preview"):
        assistant = self.client.beta.assistants.create(
            name=name,
            instructions=instructions,
            model=model_name,
            tools=[{"type": "file_search"}]
        )
        self.assistant_id = assistant.id
        logger.info(f"创建助手 {assistant.id} 成功")
        return assistant.id
    def get_message_memory(self, thread_id):
        """Get the memory of a thread"""
        messages = []
        for m in self.client.beta.threads.messages.list(thread_id=thread_id, order="asc"):
            messages.append({"role": m.role, "content": m.content[0].text.value})
        return messages
    def check_asst_file(self) -> bool:
        """
        检查assistant是否有文件
        :return:
        """
        vector_store_ids = self.get_vector_store_ids()
        if not vector_store_ids:
            return False
        vector_files = self.client.beta.vector_stores.files.list(vector_store_ids[0])
        if vector_files.data:
            return True
        return False
    def chat(self, session_id: str, content: str) -> str:
        """
        用户发送消息，调用openai的接口，返回回复
        :param session_id: 由{app_type}~{robot_id}~{operatorOpenId}组成
        :param content:
        :return:
        """
        #检查同步文件是否完成
        # if not self.thread_map:
        vector_store_ids = self.get_vector_store_ids()
        if not vector_store_ids:
            logger.error(f"[asst_id={self.assistant_id}]:助手没有关联的向量库")
            return "助手还未关联向量库，请稍后再试", False
        vector_store_id = vector_store_ids[0]
        vector_store_files = self.client.beta.vector_stores.files.list(vector_store_id, filter="in_progress")
        if vector_store_files.data:
            return "同步文件仍在处理中，请稍后再试", False

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
        run = self.client.beta.threads.runs.create_and_poll(
            thread_id=thread_id,
            assistant_id=self.assistant_id
        )

        if run.status == "completed":
            messages = self.client.beta.threads.messages.list(thread_id=thread_id, limit=1)
            logger.debug(f"[asst_id={self.assistant_id}][thread_id={thread_id}][session_id={session_id}][run_id={run.id}]: {messages.data[0].content[0]}")
            message_content = messages.data[0].content[0].text
            if message_content.annotations:
                message_content = self.process_annotation(message_content)
            # 判断是否包含答案
            has_answer_key = ["上述问题无法在标准知识库中找到答案", "在标准知识库中未能找到明确答案",
                              "上述问题无法在标凈知识库找到答案", "上述问题无法在标净知识库找到答案",
                              "无法在标准知识库中找到更具体的答案"]
            has_answer = not any(phrase in message_content.value for phrase in has_answer_key)

            return message_content.value, has_answer
        if run.status == "failed":
            logger.error(f"[asst_id={self.assistant_id}][run_id={run.id}][session_id={session_id}]状态：{run.status}. 明细:\n{run.last_error.message}")
        else:
            logger.error(f"[asst_id={self.assistant_id}][run_id={run.id}][session_id={session_id}]状态：{run.status}.")
        return None, False

    def process_annotation(self, message_content):
        annotations = message_content.annotations
        citations = []
        citation_index = 0
        file_to_index = {}  # 字典来记录文件名和对应的索引
        try:
            process_content = message_content.value
            for annotation in annotations:
                file_citation = getattr(annotation, 'file_citation', None)
                if not file_citation:
                    # 如果没有 file_citation，直接去掉 annotation.text
                    process_content = process_content.replace(annotation.text, "")
                else:
                    placeholder = f"{{{{citation_{citation_index}}}}}"
                    process_content = process_content.replace(annotation.text, placeholder)

                    # 查询文件链接
                    query_data = self.database.query_data(self.table_class, filters={"file_id": file_citation.file_id,
                                                                                     "assistant_id": self.assistant_id})
                    if query_data:
                        url = query_data[0].url
                    else:
                        url = ""
                    cited_file = self.client.files.retrieve(file_citation.file_id)
                    if file_citation.file_id not in file_to_index:
                        # 如果文件id不在字典中，添加并更新索引
                        file_to_index[file_citation.file_id] = citation_index
                        citations.append(f'[{citation_index}] {cited_file.filename} [{url}]')
                        citation_index += 1
                    else:
                        # 如果文件名已在字典中，使用已有的索引
                        existing_index = file_to_index[file_citation.file_id]
                        process_content = process_content.replace(f"{{{{citation_{citation_index}}}}}",
                                                                  f"{{{{citation_{existing_index}}}}}")
            # 最后一次性替换所有的占位符
            for key, index in file_to_index.items():
                process_content = process_content.replace(f"{{{{citation_{index}}}}}", f"[{index}]")
            message_content.value = process_content
            if citations:
                message_content.value += "\n\n" + "\n".join(citations)
        except:
            logger.error(f"[asst_id={self.assistant_id}]：助手返回内容存在问题：{message_content}\n {traceback.format_exc()}")
        return message_content

    def delete_vector_store_file(self, vector_store_id: str, file_id: str) -> bool:
        """
        删除向量库中的文件
        :param vector_store_id (str): 向量库 ID
        :param file_id (str): 文件 ID
        :return bool: 是否删除成功
        """
        try:
            deleted_file = self.client.beta.vector_stores.files.delete(
                vector_store_id=vector_store_id, file_id=file_id
            )
            if deleted_file.deleted:
                logger.debug(f"[asst_id={self.assistant_id}]：在 OpenAI 向量库 '{vector_store_id}' 中删除文件成功: {deleted_file}")
                return True
            logger.error(f"[asst_id={self.assistant_id}]：在 OpenAI 向量库 '{vector_store_id}' 中删除文件失败: {deleted_file}")
            return False
        except NotFoundError:
            logger.info(f"[asst_id={self.assistant_id}]：OpenAI 向量库 '{vector_store_id}'中不存在 '{file_id}' 文件, 已跳过删除")
            return True
        except Exception as e:
            logger.error(f"[asst_id={self.assistant_id}]：删除 OpenAI 向量库 '{vector_store_id}' 文件 '{file_id}' 失败: {e}")
            return False

    def delete_openai_file(self, file_id: str) -> bool:
        """
        删除 OpenAI 文件
        :param client (openai.Client): OpenAI 客户端实例
        :param file_id (str): 文件 ID
        :return bool: 是否删除成功
        """
        try:
            #删除数据库中文件id对应的信息
            self.database.delete_data(self.table_class, filters={"file_id": file_id, "assistant_id": self.assistant_id})
            deleted_file = self.client.files.delete(file_id)
            if deleted_file.deleted:
                logger.debug(f"[asst_id={self.assistant_id}]：在 OpenAI 文件中删除文件成功: {deleted_file}")
                return True
            logger.error(f"[asst_id={self.assistant_id}]：在 OpenAI 文件中删除文件失败: {deleted_file}")
            return False
        except NotFoundError:
            logger.info(f"[asst_id={self.assistant_id}]：OpenAI 文件 '{file_id}' 不存在, 已跳过删除")
            return True
        except Exception as e:
            logger.error(f"[asst_id={self.assistant_id}]：删除 OpenAI 文件 '{file_id}' 失败: {e}")
            return False

    def empty_files(self) -> bool:
        """
        清空assistant的文件
        :return: 是否清空了文件
        """
        try:
            vector_store_ids = self.get_vector_store_ids()
            if not vector_store_ids:
                logger.info(f"[asst_id={self.assistant_id}]：助手没有关联的向量库")
                return True
            # 删除第一个向量库之外的所有向量库
            if len(vector_store_ids) > 1:
                for vector_store_id in vector_store_ids[1:]:
                    deleted_vector_store = self.client.beta.vector_stores.delete(vector_store_id=vector_store_id)
                    if not deleted_vector_store.deleted:
                        logger.error(
                            f"[asst_id={self.assistant_id}]：删除向量库 '{deleted_vector_store.id}' 失败, 请后续手动删除并重新同步数据"
                        )
                    else:
                        logger.info(f"[asst_id={self.assistant_id}]: 已删除向量库 '{deleted_vector_store.id}'")

            vector_store_id = vector_store_ids[0]

            # 获取向量库下的文件
            vector_store_files = []
            after = None
            limit = 100
            while True:
                response = self.client.beta.vector_stores.files.list(
                    vector_store_id=vector_store_id,
                    limit=limit,
                    after=after
                )
                vector_store_files.extend(response.data)
                if len(response.data) < limit:
                    break
                after = response.data[-1].id


            is_processing_files = any(
                file.status != "completed" for file in vector_store_files
            )
            failed_vector_store_files = []
            failed_openai_files = []

            # 删除向量库和 OpenAI 文件
            for file in vector_store_files:
                vector_store_deleted = self.delete_vector_store_file(
                    vector_store_id, file.id
                )
                if not vector_store_deleted:
                    failed_vector_store_files.append(file.id)

                openai_deleted = self.delete_openai_file(file.id)
                if not openai_deleted:
                    failed_openai_files.append(file.id)
            # 查看向量库是否过期
            check_status_vector_store = self.client.beta.vector_stores.retrieve(
                vector_store_id=vector_store_id
            )
            is_expired = check_status_vector_store.status =="expired"
            if not is_expired:
                # 更新向量库名称
                self.client.beta.vector_stores.update(
                    vector_store_id=vector_store_id,
                    name=self.topic,
                    expires_after={
                        "anchor": "last_active_at",
                        "days": 7
                    }
                )

            success_count = len(vector_store_files) - len(failed_vector_store_files) #成功删除的文件数量

            # 删除整个向量库
            if is_processing_files or failed_vector_store_files or failed_openai_files or is_expired:
                logger.info(
                    f"[asst_id={self.assistant_id}]：向量库 '{vector_store_id}' 下的部分文件正在处理中或无法正常删除, 强制删除整个向量库"
                )
                deleted_vector_store = self.client.beta.vector_stores.delete(
                    vector_store_id=vector_store_id
                )
                if not deleted_vector_store.deleted:
                    logger.error(
                        f"[asst_id={self.assistant_id}]：删除向量库 '{deleted_vector_store.id}' 失败, 请后续手动删除并重新同步数据"
                    )
                else:
                    success_count = len(vector_store_files)

            logger.info(
                f"[asst_id={self.assistant_id}]：已清空助手的文件: {success_count}/{len(vector_store_files)}"
            )
            return True
        except Exception as e:
            logger.error(f"[asst_id={self.assistant_id}]：清空助手文件失败：{e}\n{traceback.format_exc()}")
            return False

    def create_vs(self,file_paths_and_urls: list) -> bool:
        """
        创建向量库并上传文件
        :param file_paths: url和文件路径
        :return: 是否上传成功
        """
        vector_store_ids = self.get_vector_store_ids()
        if not vector_store_ids:
            vector_store = self.client.beta.vector_stores.create(
                name=self.topic,
                expires_after={
                    "anchor": "last_active_at",
                    "days": 7
                })
            vector_store_ids = [vector_store.id]
            assistant = self.client.beta.assistants.update(
                assistant_id=self.assistant_id,
                tool_resources={"file_search": {"vector_store_ids": vector_store_ids}},
            )
        elif len(vector_store_ids) > 1:
            assistant = self.client.beta.assistants.update(
                assistant_id=self.assistant_id,
                tool_resources={"file_search": {"vector_store_ids": [vector_store_ids[0]]}},
            )
        return self.upload_file(file_paths_and_urls,vector_store_ids[0])

    def upload_file(self,file_paths_and_urls: list, vector_store_id: str) -> bool:
        file_streams = []
        results = []
        try:
            for url, path in file_paths_and_urls:
                file_streams.append((url, open(path, "rb")))
            logger.debug(f"[asst_id={self.assistant_id}]：上传{len(file_paths_and_urls)}个文件到向量库 '{vector_store_id}'")
            # 上传 files
            max_concurrency = 5
            with ThreadPoolExecutor(max_workers=max_concurrency) as executor:
                futures = {
                    executor.submit(
                        self.client.files.create,
                        file=file,
                        purpose="assistants",
                    ): url
                    for url, file in file_streams
                }

            for future in as_completed(futures):
                url = futures[future]
                exc = future.exception()
                if exc:
                    raise exc

                results.append((url, future.result()))
            # 将 file_id 和url的对应关系储存在数据库中
            data_list = [{
                'assistant_id': self.assistant_id,
                'file_id': file_ins.id,
                'url': file_url
            } for file_url, file_ins in results]
            self.database.batch_insert_data(self.table_class, data_list)
            # 将files 添加到vector store
            batch_size = 500
            file_ids = [f.id for _, f in results]
            total_files = len(file_ids)
            successful_files = 0

            for i in range(0, total_files, batch_size):
                batch = file_ids[i:i + batch_size]
                file_batch = self.client.beta.vector_stores.file_batches.create_and_poll(
                    vector_store_id=vector_store_id,
                    file_ids=batch
                    # chunking_strategy=chunking_strategy
                )
                if file_batch.status == "completed":
                    successful_files += file_batch.file_counts.completed
                    logger.info(
                        f"[asst_id={self.assistant_id}]：成功上传第 {i // batch_size + 1} 批文件：{file_batch.file_counts}")
                else:
                    logger.error(
                        f"[asst_id={self.assistant_id}]：第 {i // batch_size + 1} 批文件上传失败，文件上传终止，状态{file_batch.status}：{file_batch.file_counts}")
                    return False

            logger.info(f"[asst_id={self.assistant_id}]：所有文件处理完成。最终成功上传{successful_files}/{total_files}")
            if successful_files != total_files:
                # 当前这个错误暂时无法处理，暂时算作上传成功
                logger.error(f"[asst_id={self.assistant_id}]：{total_files-successful_files}个文件上传失败，请重新同步")
            return True
        finally:
            # 确保所有文件都被关闭
            for _, file_stream in file_streams:
                file_stream.close()

    def save_qa_to_database(self, session_id: str = "", msg_id: str = "", topic_name: str = "", question: str = "",
                             answer: str = "", has_answer: bool = False, asker: str = "", source: int = 0) -> None:
        has_answer = '是' if has_answer else '否'
        upload_data = {'session_id': session_id, 'msg_id': msg_id, 'topic_name': topic_name, 'question': question,
                       'answer': answer, 'has_answer': has_answer, 'asker': asker, 'source': source}
        self.database.insert_data(QARecord, upload_data)
        logger.info(f"[asst_id={self.assistant_id}]：问答数据录入成功")



    def del_assistant(self) -> None:
        """
        删除助手
        """
        try:
            # 删除助手下的所有文件和向量库
            self.empty_files()
            vector_store_ids = self.get_vector_store_ids()
            if vector_store_ids:
                for vector_store_id in vector_store_ids:
                    self.client.beta.vector_stores.delete(vector_store_id=vector_store_id)
            # 删除助手
            self.client.beta.assistants.delete(self.assistant_id)
            logger.info(f"删除助手 '{self.assistant_id}' 成功")
            self.assistant_id = None
        except:
            logger.error(f"删除助手 '{self.assistant_id}' 失败")

    def del_all_threads(self) -> None:
        """
        删除所有thread
        """
        for session_id in self.thread_map.keys():
            thread_id = self.thread_map.get(session_id)
            self.client.beta.threads.delete(thread_id)
        self.thread_map = {}
    def del_thread(self,session_id) -> None:
        """
        删除thread
        """
        if session_id in self.thread_map:
            thread_id = self.thread_map.get(session_id)
            self.client.beta.threads.delete(thread_id)
            del self.thread_map[session_id]
    def get_thread_id(self,session_id) -> str:
        """
        获取thread_id
        """
        return self.thread_map.get(session_id)

