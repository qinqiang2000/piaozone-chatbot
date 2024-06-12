import os
import sys
from typing import Optional, List
from enum import Enum

from langchain.embeddings.openai import OpenAIEmbeddings
from langchain_openai import AzureOpenAIEmbeddings
from langchain.docstore.document import Document
import weaviate

from src.tools.rag.store.simple_vstore import SimpleVectorStore
from src.tools.rag.base_rag import RAGEmbeddingType, RAGType
from src.utils.logger import logger



class DocStore:
    '''
    文档库
    '''

    def __init__(
            self,
            project_name: str,
            rag_config: dict,
            attributes: Optional[List[str]] = None
    ) -> None:
        rag_type = rag_config["rag_option"]
        docdb_config = rag_config["docdb_config"]
        self.project_name = project_name
        self.docdb_config = docdb_config
        if rag_type == RAGType.SIMPLE_RAG:
            # 1、初始化embedding
            try:
                embedding_config = self.docdb_config["embedding_config"]
                embedding_model = embedding_config["model_option"]
                if embedding_model == RAGEmbeddingType.OPENAI_EMB:
                    embedding_func = OpenAIEmbeddings(openai_api_key=embedding_config[embedding_model]["openai_api_key"])
                elif embedding_model == RAGEmbeddingType.AZURE_EMB:
                    embedding_func = AzureOpenAIEmbeddings(
                        azure_endpoint=embedding_config[embedding_model]["azure_openai_endpoint"],
                        openai_api_key=embedding_config[embedding_model]["azure_openai_api_key"],
                        azure_deployment=embedding_config[embedding_model]["model_name"],
                        openai_api_version=embedding_config[embedding_model]["openai_api_version"],
                    )
                else:
                    raise ValueError(f"不支持的 embedding model 选项: {embedding_model}")
            except Exception as e:
                logger.error(f"初始化向量库失败: {e}")
                raise Exception(f"初始化向量库失败: {e}")
            self.embedding_func = embedding_func
            # 2、初始化vector store
            client = weaviate.Client(url=self.docdb_config["connection_args"]["url"])
            self.doc_db = SimpleVectorStore(client=client, index_name=self.project_name,
                     text_key="text", embedding=self.embedding_func, attributes=attributes,
                     by_text=False)
        else:
            raise ValueError(f"不支持的 docdb_option 选项: {docdb_config['docdb_option']}")
    def has_project(self) -> bool:
        status = self.doc_db.has_project()
        return status
    def init_doc_store(self,documents: List[Document]) -> bool:
        """
        初始化文档数据库
        """
        is_success = self.doc_db.init_docdb(documents=documents)
        return is_success
    def partial_update_documents(self,documents: List[Document]) -> bool:
        """
        部分更新向量数据库
        """
        is_success = self.doc_db.partial_update_documents(documents=documents)
        return is_success
    def full_update_documents(self,documents: List[Document]) -> bool:
        """
        全量更新向量数据库
        """
        is_success = self.doc_db.full_update_documents(documents=documents)
        return is_success

    def search(self, query: str, doc_topk: int = 5, faq_topk: int = 5) -> tuple[List[Document], List[Document]]:
        faq_docs, doc_docs = self.doc_db.search(query=query, doc_topk=doc_topk, faq_topk=faq_topk)
        faq_res = self.postprecess_search(faq_docs)
        doc_res = self.postprecess_search(doc_docs)
        return faq_res, doc_res
    def postprecess_search(self,docs: List[Document]) -> List[Document]:
        res = []
        pages = []
        for doc in docs:
            if doc.page_content not in pages:
                res.append(doc)
                pages.append(doc.page_content)
        del pages
        return res

    def delete_project(self) -> bool:
        status = self.has_project()
        if not status:
            logger.warning(f"向量库中不存在 {self.project_name}的数据")
            return True
        return self.doc_db.delete_project()


