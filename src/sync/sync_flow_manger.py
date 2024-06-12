"""
sync_flow模块，用于串联reader和writer,目前只支持全量数据同步
"""
from enum import Enum
import traceback

from src.utils.logger import logger
from src.sync.yuque_reader import YQReader
from src.sync.sync_flow import openai_asst_sync

class SyncDestType(str, Enum):
    """同步目的地"""
    OPENAI_ASST = "openai-asst"
    # SIMPLE_RAG_ASST = "simple-rag-asst"
    # SIMPLE_VECTOR_DB = "simple_vector_db"

class SyncManager:
    DEST_TO_FLOW = {
        SyncDestType.OPENAI_ASST: openai_asst_sync.SyncFlow,
    }
    def __init__(self, yuque_config, yuque_repos, sync_configs=None):
        # 初始化 SyncFlow
        # 1. 初始化语雀读取器 YQReader
        self.yqreader = YQReader(yuque_config=yuque_config,
                                 yuque_repos=yuque_repos)
        self.sync_dict = {}
        if sync_configs is None:
            sync_configs = []
            logger.error("未设置同步配置")
        for sync_config in sync_configs:
            sync_flow_id = sync_config.get("id")
            sync_type = sync_config.get("type")
            sync_params = sync_config.get("params")
            if sync_type not in [e.value for e in SyncDestType]:
                raise Exception(f"同步配置不支持type '{sync_type}'")
            if sync_flow_id in self.sync_dict:
                raise Exception(f"同步配置id '{sync_flow_id}' 重复")
            sync_flow_class = self.DEST_TO_FLOW[sync_type]
            self.sync_dict[sync_flow_id] = sync_flow_class(yqreader=self.yqreader,**sync_params)
        logger.info(f"同步流程初始化成功")
    def update_yq_repos(self,repos):
        new_repos = [repo for repo in repos if repo not in self.yqreader.repo2tocs_map]
        # 更新语雀reader
        self.yqreader.update_tocs_list(new_repos)
    def update_sync_configs(self,new_sync_configs):
        for sync_config in new_sync_configs:
            sync_flow_id = sync_config.get("id")
            sync_type = sync_config.get("type")
            sync_params = sync_config.get("params")
            if sync_type not in [e.value for e in SyncDestType]:
                logger.error(f"同步配置不支持type '{sync_type}',请重新设置")
            if sync_flow_id in self.sync_dict:
                logger.error(f"同步配置id '{sync_flow_id}' 重复,请重新设置")
            sync_flow_class = self.DEST_TO_FLOW[sync_type]
            self.sync_dict[sync_flow_id] = sync_flow_class(**sync_params)
        logger.info(f"同步流程更新成功")

    # def sync_yq_doc_to_rag_asst(self, repo: str, toc_title: str, assistant: BaseAssistant) -> bool:
    #     """
    #     同步对应的知识库的所有文档到问答助手对应的docstore
    #     :param repo: 知识库的唯一标识
    #     :param toc_title: 目录title,对应知识库的专题库
    #     :param assistant: gpt assistant
    #     :return:
    #     """
    #     is_success = True
    #     for tool in assistant.tools.values():
    #         if getattr(tool, "rag_type", None) == RAGType.SIMPLE_RAG:
    #             if not self.sync_yq_doc_to_docdb(repo, toc_title, tool.doc_store):
    #                 is_success = False
    #     return is_success
    # def sync_yq_doc_to_docdb(self, repo: str, toc_title: str, doc_store: DocStore) -> bool:
    #     """
    #     同步对应的知识库的文档到文档数据库
    #     :param repo: 知识库的唯一标识
    #     :param toc_title: 目录title,对应知识库的专题库
    #     :param doc_store: 文档库
    #     :return:
    #     """
    #     # 1. 获取语雀知识库文档
    #     logger.info(f"开始获取语雀知识库'{toc_title}'文档...")
    #     yq_docs = self.yqreader.get_docs_for_topic_title(repo, toc_title)
    #     logger.info(f"获取语雀知识库'{toc_title}'文档成功，文档数量: {len(yq_docs)}")
    #     if not yq_docs:
    #         logger.error(f"没有语雀文档，同步'{toc_title}'数据到文档数据库'{doc_store.project_name}'失败")
    #         return False
    #     try:
    #         yq_access_url = self.yqreader.get_access_base_url(repo=repo)
    #         # 2. 转换文档
    #         docs_chunks = self.transformer(yuque_docs=yq_docs, yuque_base_url=yq_access_url)
    #         if not docs_chunks:
    #             logger.error(f"转换语雀文档失败，同步'{toc_title}'数据到文档数据库'{doc_store.project_name}'失败")
    #             return False
    #         # 3. 写入文档
    #         return self.writer(docs_chunks=docs_chunks, doc_store=doc_store)
    #     except Exception as e:
    #         logger.error(f"同步数据到文档数据库失败：{e}.{traceback.format_exc()}")
    #         return False
    #     return True

