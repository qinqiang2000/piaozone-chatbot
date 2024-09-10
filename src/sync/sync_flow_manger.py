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

