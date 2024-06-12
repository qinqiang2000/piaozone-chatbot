"""
支持简单索引和搜索的weaviate向量数据库
"""
from typing import Optional, Any, Tuple, List, Dict, Union
from uuid import uuid4
import time

from langchain.vectorstores import Weaviate
from langchain.docstore.document import Document
import traceback

from src.sync.document_transformers.simple_rag_transform import DocType, MetaKey
from src.utils.logger import logger


def _default_schema(index_name: str, text_key: str) -> Dict:
    return {
        "class": index_name,
        "properties": [
            {
                "name": text_key,
                "dataType": ["text"],
            },

        ],
    }

class SimpleVectorStore(Weaviate):
    '''
    Vector database APIs: insert, search
    '''

    def has_project(self):
        """
        检查 当前weaviate中是否有数据
        :return:
        """
        #client.schema.update_config(class_name , schema)
        return self._client.schema.exists(self._index_name)

    def init_docdb(self, documents: List[Document]) -> bool:
        """
        当不存在数据时，添加数据进行初始化
        """
        try:
            if not documents:
                logger.error(f"{self._index_name}:weaviate不存在同步数据, 请重新同步数据")
                return False
            schema = _default_schema(self._index_name, self._text_key)
            self._client.schema.create_class(schema)
            ##
            faq_documnets = [d for d in documents if d.metadata[MetaKey.DOC_TYPE.value] == DocType.FAQ.value]
            table_documents = [d for d in documents if d.metadata[MetaKey.DOC_TYPE.value] == DocType.TABLE.value]
            doc_documents = [d for d in documents if d.metadata[MetaKey.DOC_TYPE.value] == DocType.DOC.value]
            if faq_documnets:
                is_success = self.add_batch_texts(faq_documnets, 2000)
                if not is_success:
                    return False
            if table_documents:
                is_success = self.add_batch_texts(table_documents, 3000)
                if not is_success:
                    return False
            if doc_documents:
                is_success = self.add_batch_texts(doc_documents, 100)
                if not is_success:
                    return False
        except Exception as e:
            logger.error(f"{self._index_name}:weaviate初始化数据失败: {e}.{traceback.format_exc()}")
            return False
        return True
    def add_batch_texts(self, documents: List[Document], batch_size: int) -> List[str]:
        doc_len = len(documents)
        logger.debug(f"weaviate待添加数据数量: {doc_len}")
        for i in range(0, doc_len, batch_size):
            texts = [d.page_content for d in documents[i:i + batch_size]]
            metadatas = [d.metadata for d in documents[i:i + batch_size]]
            add_ids = self.add_texts(texts=texts, metadatas=metadatas)
            logger.debug(f"{self._index_name}:weaviate:添加数据数量: {len(add_ids)}")
            if len(add_ids) != len(texts):
                logger.error(f"{self._index_name}:weaviate添加数据存在错误, 请重新同步数据")
                return False
            time.sleep(45)
        return True

    def delete_documents_for_slug(self, slugs: List[str]) -> bool:
        """
        基于slug删除数据
        """
        try:
            del_result = self._client.batch.delete_objects(
                class_name=self._index_name,
                where={
                    "path": ["slug"],
                    "operator": "ContainsAny",
                    "valueTextArray": slugs
                }
            )
            if "results" in del_result:
                fail_num = del_result["results"]["failed"]
                if fail_num > 0:
                    logger.error(f"weaviate删除部分数据失败, 失败数量: {fail_num}，请重新同步数据")
                    return False

        except Exception as e:
            logger.error(f"weaviate删除数据失败：{e}.{traceback.format_exc()}")
            return False
        return True
    # 全量更新数据
    def full_update_documents(self, documents: List[Document]) -> bool:
        """
        全量更新数据
        :param documents: 新数据集
        :return: 是否更新成功
        """
        try:
            if not documents:
                logger.error("weaviate不存在同步数据, 请重新同步数据")
                return False
            # 1、删除现存数据集中的所有数据
            is_del = self.delete_project()
            if not is_del:
                logger.error(f"weaviate删除【{self._index_name}】数据失败")
                return False
            # 2、添加新数据
            schema = _default_schema(self._index_name, self._text_key)
            self._client.schema.create_class(schema)

            faq_documnets = [d for d in documents if d.metadata[MetaKey.DOC_TYPE.value] == DocType.FAQ.value]
            table_documents = [d for d in documents if d.metadata[MetaKey.DOC_TYPE.value] == DocType.TABLE.value]
            doc_documents = [d for d in documents if d.metadata[MetaKey.DOC_TYPE.value] == DocType.DOC.value]
            if faq_documnets:
                is_success = self.add_batch_texts(faq_documnets, 2000)
                if not is_success:
                    return False
            if table_documents:
                is_success = self.add_batch_texts(table_documents, 3000)
                if not is_success:
                    return False
            if doc_documents:
                is_success = self.add_batch_texts(doc_documents, 100)
                if not is_success:
                    return False
        except Exception as e:
            logger.error(f"weaviate更新数据失败: {e}.{traceback.format_exc()}")
            return False
        return True

    def partial_update_documents(self, documents: List[Document]) -> bool:
        """
        部分更新数据，只更新修改过的数据
        :param documents: 新数据集
        :return: 是否更新成功
        """
        try:
            # 1、获取现存数据集中的所有数据的"slug","title","version"字段
            query_result = self._client.query.get(self._index_name, ["slug", "title", "version"]).do()
            if "errors" in query_result:
                looger.error(f"weaviate查询向量库{self._index_name}错误: {query_result['errors']}")
                return False
            old_docs_data = dict()
            for res in query_result["data"]["Get"][self._index_name]:
                slug = res.pop("slug")
                old_docs_data[slug] = res
            # 2、比较新数据集和现存数据集中的数据
            new_docs_slugs = set([d.metadata["slug"] for d in documents]) # 新数据集中的所有数据的"slug"字段
            delete_doc_slugs = list(set(old_docs_data.keys()) - new_docs_slugs) # 需要删除的数据的"slug"字段
            add_doc_slugs = set()
            update_doc_slugs = set()
            for doc in documents:
                slug = doc.metadata["slug"]
                if slug in old_docs_data:
                    if (doc.metadata["title"] != old_docs_data[slug]["title"] or
                            doc.metadata["version"] != old_docs_data[slug]["version"]):
                        update_doc_slugs.add(slug)
                else:
                    add_doc_slugs.add(slug)
            add_doc_slugs = list(add_doc_slugs)
            update_doc_slugs = list(update_doc_slugs)
            # 3、删除需要删除的数据
            delete_doc_slugs = delete_doc_slugs + update_doc_slugs
            # 如果delete_doc_slugs数量>10000,做切分，如果delete_doc_slugs数量<=10000,直接删除
            is_del = True
            if len(delete_doc_slugs) > 10000:
                for i in range(0, len(delete_doc_slugs), 10000):
                    is_part_del = self.delete_documents_for_slug(delete_doc_slugs[i:i + 10000])
                    if not is_part_del:
                        is_del = False
            elif delete_doc_slugs:
                is_del = self.delete_documents_for_slug(delete_doc_slugs)
            if not is_del:
                return False
            # 4、添加新数据
            faq_documnets = []
            table_documents = []
            doc_documents = []
            for doc in documents:
                if doc.metadata["slug"] in add_doc_slugs or doc.metadata["slug"] in update_doc_slugs:
                    if doc.metadata[MetaKey.DOC_TYPE.value] == DocType.FAQ.value:
                        faq_documnets.append(doc)
                    elif doc.metadata[MetaKey.DOC_TYPE.value] == DocType.TABLE.value:
                        table_documents.append(doc)
                    elif doc.metadata[MetaKey.DOC_TYPE.value] == DocType.DOC.value:
                        doc_documents.append(doc)
            if faq_documnets:
                is_success = self.add_batch_texts(faq_documnets, 2000)
                if not is_success:
                    return False
            if table_documents:
                is_success = self.add_batch_texts(table_documents, 3000)
                if not is_success:
                    return False
            if doc_documents:
                is_success = self.add_batch_texts(doc_documents, 100)
                if not is_success:
                    return False
        except Exception as e:
            logger.error(f"weaviate更新数据失败: {e}.{traceback.format_exc()}")
            return False
        return True

    def search(self, query: str, doc_topk: int = 5, faq_topk: int = 5) -> tuple[List[Document], List[Document]]:
        """
        基于问题查询数据
        :param query: 问题
        :param doc_topk: 文档查询返回的最大数量
        :param faq_topk: faq查询返回的最大数量
        :return: 查询结果
        """
        embedding = self._embedding.embed_query(query)
        faq_res = self.search_for_condition(
            embedding=embedding,
            topk=faq_topk,
            condition={
                "path": [MetaKey.DOC_TYPE.value],
                "operator": "Equal",
                "valueText": DocType.FAQ.value}
        )
        doc_res = self.search_for_condition(
            embedding=embedding,
            topk=doc_topk,
            condition={
                "path": [MetaKey.DOC_TYPE.value],
                "operator": "ContainsAny",
                "valueText": [DocType.TABLE.value, DocType.DOC.value]}
        )
        return faq_res, doc_res
    def search_for_condition(self, embedding: str, condition: dict, topk: int = 5 ) -> List[Document]:
        """
        根据条件查询数据
        :param embedding: 问题的embedding
        :param condition: 查询条件
        :param topk: 查询返回的最大数量
        :return: 查询结果
        """
        docs = self.similarity_search_by_vector(
            embedding=embedding,
            k=topk,
            where_filter=condition
        )
        res = []
        for doc in docs:
            if 'text' in doc.metadata:
                del doc.metadata['text']
            res.append(doc)
        return res

    def delete_project(self) -> bool:
        """
        删除向量数据库中的所有数据
        :return: 是否删除成功
        """
        try:
            if self.has_project():
                self._client.schema.delete_class(self._index_name)
                logger.info(f"删除weaviate中 {self._index_name} 的所有数据成功")
            return True
        except Exception as e:
            logger.error(f"删除weaviate中 {self._index_name} 的所有数据失败: {e}")
            return False

