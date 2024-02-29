"""
sync_flow模块，用于串联reader和writer,目前只支持全量数据同步
"""
import traceback

import src.utils.common_utils as utils
from src.utils.logger import logger
from src.sync.yuque_reader import YQReader
from src.sync.document_transformers import OpenAIAsstTransformer
from src.sync.document_writers import OpenAIAsstWriter


class SyncFlow:
    transformer_map = {
        "openai_asst": OpenAIAsstTransformer,
        "azure_openai_asst": OpenAIAsstTransformer,
    }
    writer_map = {
        "openai_asst": OpenAIAsstWriter,
        "azure_openai_asst": OpenAIAsstWriter
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
        assert sync_destination_name in self.transformer_map, f"不支持的同步目标: {sync_destination_name}, 目前支持的同步目标: {self.transformer_map.keys()}"
        # 2. 初始化转换器
        self.transformer = self.transformer_map[sync_destination_name](file_num_limit=file_num_limit,
                                                                       file_token_limit=file_token_limit)
        # 3. 初始化写入器
        if sync_destination_name in ["azure_openai_asst"]:
            self.writer = self.writer_map[sync_destination_name](use_azure=True, **kwargs)
        else:
            self.writer = self.writer_map[sync_destination_name](**kwargs)

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

