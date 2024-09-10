"""
sync_flow模块，用于串联reader和writer,目前只支持全量数据同步
"""
from enum import Enum
import traceback

from src.utils.logger import logger
from src.sync.yuque_reader import YQReader
from src.sync.document_transformers import OpenAIAsstTransformer
from src.sync.document_writers import OpenAIAsstWriter
from qa_assistant.base_assistant import BaseAssistant

class SyncFlow:

    def __init__(self, yqreader:YQReader,file_num_limit: int=None, file_token_limit: int=None):
        self.sync_type = "openai-asst"
        self.yqreader = yqreader
        # 2. 初始化转换器
        self.transformer = OpenAIAsstTransformer(file_num_limit=file_num_limit,file_token_limit=file_token_limit)
        # 3. 初始化写入器
        self.writer = OpenAIAsstWriter()
        logger.info(f"语雀到 openai assistant 的同步流程初始化成功")

    def sync_yq_doc_to_dest(self, yq_info: list, assistant: BaseAssistant) -> bool:
        """
        同步对应的知识库的所有文档到问答助手(可能存在多个知识库)
        :param yq_info: [(repo:知识库的唯一标识, toc_title: 目录title,对应知识库的专题库)]
        :param assistant: gpt assistant
        :return: bool :是否同步成功
        """
        if not assistant or not yq_info:
            logger.error(
                f"同步数据到gpt assistant失败,请检查助手以及当前语雀知识库信息'{yq_info}'是否正确配置")
            return False
        # 1.清空缓存文件
        self.transformer.empty_cache(assistant.assistant_id)
        # 1. 获取语雀知识库文档
        try:
            all_asst_docs = []
            for repo, toc_title in yq_info:
                logger.info(f"[asst_id={assistant.assistant_id}]：开始获取语雀知识库'{toc_title}'文档...")
                yq_docs = self.yqreader.get_docs_for_topic_title(repo, toc_title)
                if not yq_docs:
                    logger.warning(f"[asst_id={assistant.assistant_id}]：语雀知识库'{toc_title}'未获取到文档")
                else:
                    logger.info(
                        f"[asst_id={assistant.assistant_id}]：获取语雀知识库'{toc_title}'文档成功，文档数量: {len(yq_docs)}")
                # 2. 转换文档
                base_url = self.yqreader.get_access_base_url(repo)
                # file_name_prefix = f"{repo}-{toc_title}"
                asst_docs = self.transformer(yq_docs, assistant.assistant_id, base_url, toc_title)
                all_asst_docs.extend(asst_docs)
            # 3. 写入文档
            return self.writer(all_asst_docs, assistant)
        except Exception as e:
            logger.error(f"[asst_id={assistant.assistant_id}]：同步数据到gpt assistant 失败：{e}.{traceback.format_exc()}")
            return False
        return True

