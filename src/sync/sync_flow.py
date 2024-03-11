"""
sync_flow模块，用于串联reader和writer,目前只支持全量数据同步
"""
from enum import Enum
import traceback

from src.utils.logger import logger
from src.sync.yuque_reader import YQReader
from src.sync.document_transformers import OpenAIAsstTransformer
from src.sync.document_writers import OpenAIAsstWriter


class SyncDestType(str, Enum):
    """同步目的地"""
    OPENAI_ASST = "openai-asst"
    AZURE_ASST = "azure-asst"

class SyncFlow:
    DEST_TO_TRANSFORMER = {
        SyncDestType.OPENAI_ASST: OpenAIAsstTransformer,
        SyncDestType.AZURE_ASST: OpenAIAsstTransformer
    }
    DEST_TO_WRITER = {
        SyncDestType.OPENAI_ASST: OpenAIAsstWriter,
        SyncDestType.AZURE_ASST: OpenAIAsstWriter
    }
    def __init__(self, yuque_base_url, yuque_namespace, yuque_auth_token, yuque_request_agent, sync_destination_name,
                 file_num_limit,file_token_limit, yuque_repos, **kwargs):
        # 初始化 SyncFlow
        # 1. 初始化语雀读取器 YQReader
        self.yqreader = YQReader(yuque_base_url=yuque_base_url,
                                 yuque_namespace=yuque_namespace,
                                 yuque_auth_token=yuque_auth_token,
                                 yuque_request_agent=yuque_request_agent,
                                 yuque_repos=yuque_repos)
        assert sync_destination_name in self.DEST_TO_TRANSFORMER, f"不支持的同步目标: {sync_destination_name}, 目前支持的同步目标: {self.DEST_TO_TRANSFORMER.keys()}"
        # 2. 初始化转换器
        self.transformer = self.DEST_TO_TRANSFORMER[sync_destination_name](file_num_limit=file_num_limit,
                                                                           file_token_limit=file_token_limit)
        # 3. 初始化写入器
        if sync_destination_name in [SyncDestType.AZURE_ASST]:
            self.writer = self.DEST_TO_WRITER[sync_destination_name](use_azure=True, **kwargs)
        else:
            self.writer = self.DEST_TO_WRITER[sync_destination_name](**kwargs)
    def update_sync_config(self,repos):
        new_repos = [repo for repo in repos if repo not in self.yqreader.repo2tocs_map]
        # 更新语雀reader
        self.yqreader.update_tocs_list(new_repos)

    def sync_yq_topicdata_to_asst(self, repo: str, toc_title: str, assistant_id: str = None) -> bool:
        """
        同步对应的知识库的所有文档到问答助手
        :param repo: 知识库的唯一标识
        :param toc_title: 目录title,对应知识库的专题库
        :param assistant_id: gpt assistant id
        :return:
        """
        # 1. 获取语雀知识库文档
        logger.info(f"开始获取语雀知识库'{toc_title}'文档...")
        yq_docs = self.yqreader.get_docs_for_topic_title(repo, toc_title)
        logger.info(f"获取语雀知识库'{toc_title}'文档成功，文档数量: {len(yq_docs)}")
        if not yq_docs or not assistant_id:
            logger.error(f"同步数据到gpt assistant失败，参数有误: {assistant_id}")
            return False
        try:
            # 2. 转换文档
            asst_docs = self.transformer(yq_docs, assistant_id)
            # 3. 写入文档
            return self.writer(asst_docs, assistant_id)
        except Exception as e:
            logger.error(f"同步数据到gpt assistant失败：{e}.{traceback.format_exc()}")
            return False
        return True

