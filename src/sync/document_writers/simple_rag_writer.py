"""
Simple Rag writer模块，提供同步数据(分块数据，向量数据)到weaviate向量库的功能
"""

import traceback

from src.tools.rag.store import DocStore
from src.utils.logger import logger

class SimpleRagWriter:
    def __call__(self,docs_chunks: list, doc_store: DocStore) -> bool:
        if not docs_chunks:
            logger.warning(f"没有数据需要同步到'{doc_store.project_name}'文档库")
            return True
        if not doc_store.has_project():
            is_success = doc_store.init_doc_store(documents=docs_chunks)
        else:
            is_success = doc_store.partial_update_documents(documents=docs_chunks)
        logger.debug(f"同步数据到{doc_store.project_name}{'成功' if is_success else '失败'}。")
        return is_success
