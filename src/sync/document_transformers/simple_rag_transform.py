"""
Simple Rag Transfomer模块，提供专用于简单版rag的文档清洗、文档切块、文档向量化功能
"""

import json
import re
import os
from typing import List
from enum import Enum

import traceback
import pandas as pd
from langchain.docstore.document import Document
from langchain.text_splitter import MarkdownTextSplitter
from langchain.text_splitter import CharacterTextSplitter


from src.utils import data_process
from src.utils.logger import logger
class DocType(str,Enum):
    FAQ = "faq"
    TABLE = "table"
    DOC = "doc"
class MetaKey(str,Enum):
    DOC_ID = "doc_id"
    SLUG = "slug"
    TITLE = "title"
    VERSION = "version"
    DOC_TYPE = "doc_type"
    START_INDEX = "start_index"
    SHEET_NAME = "sheet_name"
    DOC_URL = "doc_url"

class Metadata:
    # 文档元数据, 用于标记文档的基本信息,以MetaKey为key
    def __init__(self, doc_id: int, slug: str, title: str,
                 version: str, doc_type: str, doc_url:str,start_index: int = 0,
                 sheet_name: str = ""):
        self.doc_id = doc_id
        self.slug = slug
        self.title = title
        self.version = version
        self.doc_type = doc_type
        self.start_index = start_index #chunk的起始位置/ table的行数
        self.sheet_name = sheet_name
        self.doc_url = doc_url

    def to_dict(self):
        return {
            "doc_id": self.doc_id,
            "slug": self.slug,
            "title": self.title,
            "version": self.version,
            "doc_type": self.doc_type,
            "start_index": self.start_index,
            "sheet_name": self.sheet_name,
            "doc_url": self.doc_url
        }

class SimpleRagTransformer:
    def __init__(self, docdb_config: dict):
        self.markdown_splitter = MarkdownTextSplitter(chunk_size=docdb_config["chunk_size"],
                                                      chunk_overlap=docdb_config["chunk_overlap"],
                                                      length_function=len,
                                                      keep_separator=True,
                                                      add_start_index=True)
        self.tmp_path = "tmp"
    def __call__(self,yuque_docs: List[dict],yuque_base_url: str):
        """
        对语雀文档进行处理
        :param yuque_docs: 语雀文档
        """
        # 1、将文档拆分为普通文档、表格文档、faq文档
        docs, table_docs, faq_docs = self.split_docs(yuque_docs)
        # 2、保存faq文档
        faq_chunks = self.transform_faq(faq_docs, yuque_base_url)
        table_chunks = self.transform_table_docs(table_docs,yuque_base_url)
        docs_chunks = self.transform_docs(docs,yuque_base_url)
        if faq_chunks:
            docs_chunks.extend(faq_chunks)
        if table_chunks:
            docs_chunks.extend(table_chunks)
        return docs_chunks

    def split_docs(self, yq_docs: List[dict]):
        """
        拆分文档为普通文档、表格文档、faq文档
        :param yq_docs: 语雀文档
        """
        docs = []
        table_docs = []
        faq_docs = []
        for doc in yq_docs:
            if (doc["format"] == "markdown" or doc["format"] == "lake") \
                    and "faq" in doc["title"].lower() and doc["body"]:
                faq_docs.append(doc)
            elif doc["format"] == "lake" and doc["body"]:
                docs.append(doc)
            elif doc["format"] == "lakesheet" and doc["body_sheet"]:
                table_docs.append(doc)
        return docs, table_docs, faq_docs
    def save_data(self, data, file_name,data_type="doc"):
        """
        保存数据
        :param data: 数据
        :param file_name: 文件名
        :param data_type: 数据类型
        """
        file_name = re.sub("\s","",file_name.strip())
        file_name = file_name.replace("|","_")
        if not os.path.exists(self.tmp_path):
            os.makedirs(self.tmp_path)
        save_path = os.path.join(self.tmp_path, f"{file_name}.md") if data_type == "doc" else os.path.join(self.tmp_path, f"{file_name}.csv")
        if os.path.exists(save_path):
            logger.warning(f"文件{save_path}已存在，将被覆盖")
        if data_type == "doc":
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(data)
        else:
            data.to_csv(save_path, index=False)

    def transform_faq(self,faq_docs: List[dict], yuque_base_url: str) -> List[Document]:
        """
        处理faq文档
        :param faq_docs: faq文档
        :param yuque_base_url: 语雀文档的base url
        :return: faq chunks
        """
        if not faq_docs:
            logger.warning("本次同步的知识库文档中没有符合faq规定的相关文档，请检查")
            return []
        doc_chunks = []
        for doc in faq_docs:
            if doc["published_at"] is None and not doc["body"].strip():
                continue
            # 1. 对mardown文本进行基本处理
            body = data_process.md_basic_process(doc["body"])  # (不能处理\n否则会导致分块错误)
            # 分离文本和表格
            data = data_process.separate_markdown_text_table(body)
            for chunk in data:
                if chunk["type"] == "table":
                    table_header = data_process.yq_md_text_process(chunk["text"][0]).replace("\n","").strip("|").split("|")
                    table_header = [header.strip() for header in table_header]
                    # 判断表头是否符合faq格式
                    if "问题" in table_header and "答案" in table_header:
                        question_idx = table_header.index("问题")
                        answer_idx = table_header.index("答案")
                        for idx, row in enumerate(chunk["text"][2:]):
                            row = data_process.yq_md_text_process(row).strip("|").split("|")
                            metadata = Metadata(doc_id=doc["id"], slug=doc["slug"],
                                                title=doc["title"],
                                                version=str(doc.get("latest_version_id", None)),
                                                doc_type=DocType.FAQ.value,
                                                start_index=idx,
                                                doc_url=f"{yuque_base_url}/{doc['slug']}")
                            question = row[question_idx].strip()
                            answer = row[answer_idx].strip()
                            if question and answer:
                                doc_chunks.append(
                                    Document(page_content=f"问题: {row[question_idx].strip()}\n答案: {row[answer_idx].strip()}",
                                         metadata=metadata.to_dict())
                                )
            if len(doc_chunks) == 0:
                logger.warning(f"FAQ文档中没有表格：{doc['title']}")
                return []
        return doc_chunks
    def transform_table_docs(self, table_docs: List[dict],yuque_base_url: str) -> List[Document]:
        """
        处理表格文档
        :param table_docs: 表格文档
        :return:
        """
        if not table_docs:
            logger.info(f"本次同步的知识库文档中, 没有表格")
            return []

        doc_chunks = []
        # 将表格文档转换为html格式
        for doc in table_docs:
            if doc["published_at"] is None and "body_sheet" not in doc:
                continue
            sheets = json.loads(doc['body_sheet'])['data']
            for sheet in sheets:
                try:
                    table = sheet['table']
                    if not table or table == [['']]:
                        continue
                    df = pd.DataFrame(table)
                    data_process.clear_pd_nan(df)
                    rows = data_process.pd_table_to_dict(df, has_header=False)
                    self.save_data(df, f"{doc['title']}_{sheet['name']}", data_type="table")
                    for idx, row in enumerate(rows):
                        metadata = Metadata(doc_id=doc["id"], slug=doc["slug"],
                                            title=doc["title"],
                                            version=str(doc.get("latest_version_id", None)),
                                            doc_type=DocType.TABLE.value,
                                            sheet_name=sheet['name'],
                                            start_index=idx,
                                            doc_url=f"{yuque_base_url}/{doc['slug']}#{sheet['id']}")
                        # 判断是否有有效的sheet name
                        if re.search("^sheet[\s\_\-]*\d+$", sheet['name'].lower().strip()):
                            content = f"# {doc['title']}\n" + "\n".join(
                                [f"{k}: {v}" for k, v in row.items()])
                        else:
                            content = f"# {doc['title']}\n## {sheet['name']}\n"+"\n".join([f"{k}: {v}" for k, v in row.items()])
                        doc_chunks.append(Document(page_content=content, metadata=metadata.to_dict()))
                except Exception as e:
                    logger.error(f"表格文档[{doc['title']} - {sheet['name']}]转换失败：{e}.{traceback.format_exc()}")
        return doc_chunks
    def transform_docs(self, docs: List[dict], yuque_base_url: str) -> List[Document]:
        """
        处理普通文档
        :param docs: 普通文档
        :param yuque_base_url: 语雀文档的base url
        :return: doc chunks
        """
        if len(docs) == 0:
            logger.warning("语雀文档中没有符合规定的相关文档，请检查")
            return []
        doc_chunks = []
        for doc in docs:
            if doc["published_at"] is None and not doc["body"].strip():
                continue
            body = self.transform_md_body(doc["body"], doc["title"])
            doc["body"] = body
            self.save_data(body, doc["title"], data_type="doc")
            metadata = Metadata(doc_id=doc["id"], slug=doc["slug"], title=doc["title"],
                                version=str(doc.get("latest_version_id", None)), doc_type=DocType.DOC.value,
                                doc_url=f"{yuque_base_url}/{doc['slug']}")
            doc_chunks.extend(self.markdown_splitter.create_documents([doc["body"]], metadatas=[metadata.to_dict()]))
        return doc_chunks

    def transform_md_body(self,body, title):
        # 1. 对mardown文本进行基本处理
        body = data_process.md_basic_process(body) #(不能处理\n否则会导致分块错误)
        # 2. 分离markdown的文本和表格
        data = data_process.separate_markdown_text_table(body)
        # 3. 对文本部分进行处理
        for chunk in data:
            if chunk["type"] == "text":
                chunk["text"] = data_process.yq_md_text_process("\n".join(chunk["text"])) #语雀文档的文本部分需要特殊处理
            elif chunk["type"] == "table":
                chunk["text"] = "\n".join(chunk["text"])
        body = "\n".join([chunk["text"] for chunk in data])
        # 4. 对标题进行处理
        body = re.sub(r'^#{1,6}\s.+$', self.increase_level, body, flags=re.MULTILINE)
        body = f"# {title} \n" + body
        return body
    def increase_level(self,match):
        # 将标题级别升高一级
        return '#' + match.group(0)
        # heading_level = len(match.group(0).split()[0])
        # if heading_level == 6:
        #     return match.group(0)  # 如果已经是六级标题,保持不变
        # else:
        #     return '#' + match.group(0)

