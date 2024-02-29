"""
GPT Assistant Transfomer模块，提供文档清洗、文档转换功能
"""

import json
import re
import os
from typing import List

import pandas as pd

import src.utils.common_utils as utils
from src.utils.logger import logger

class OpenAIAsstTransformer:
    # 限制文件数量：20
    # 限制文件大小：512MB
    # 限制文件token数量：2000000
    FILE_NUM_LIMIT = 20
    FILE_TOKEN_LIMIT = 2000000
    def __init__(self, file_num_limit=None, file_token_limit=None):
        if file_num_limit is not None:
            self.FILE_NUM_LIMIT = file_num_limit # 20
        if file_token_limit is not None:
            self.FILE_TOKEN_LIMIT = file_token_limit # 2000000
        self.tmp_dir = os.path.join(os.path.dirname(__file__), "../../../tmp")
    def __call__(self,yuque_docs: List[dict],assistant_id: str):
        max_file_num = self.FILE_NUM_LIMIT
        # 1、将文档拆分为普通文档、表格文档、faq文档
        docs, table_docs, faq_docs = self.split_docs(yuque_docs)
        # 2、保存faq文档
        faq_paths = self.transform_faq(faq_docs, assistant_id,self.FILE_TOKEN_LIMIT, max_file_num)
        max_file_num -= len(faq_paths) if faq_paths is not None else 0
        table_docs_paths = self.transform_table_docs(table_docs, assistant_id,self.FILE_TOKEN_LIMIT, max_file_num)
        max_file_num -= len(table_docs_paths) if table_docs_paths is not None else 0
        docs_paths = self.transform_docs(docs, assistant_id, max_file_num)
        docs_paths = docs_paths if docs_paths is not None else []
        if faq_paths:
            docs_paths.extend(faq_paths)
        if table_docs_paths:
            docs_paths.extend(table_docs_paths)
        return docs_paths

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
    def divide_docs_into_chunks(self, docs: str, max_tokens_per_file: int, max_file_num: int):
        """
        基于token数量将多个文档分配为多个文件
        :param docs: 待分配的文档
        :param max_tokens_per_file: 每个文件的最大token数
        :param max_file_num: 最大文件数
        :return:
        """
        chunks = []
        current_tokens_num = utils.openai_num_tokens_from_string("\n".join(docs))
        if current_tokens_num > max_tokens_per_file:
            current_chunk = []
            current_tokens_num = 0
            for line in docs:
                # 1. 计算当前行的token数
                line_tokens_num = utils.openai_num_tokens_from_string(line)
                if line_tokens_num > max_tokens_per_file:
                    line = utils.openai_truncate_string(line, max_tokens_per_file)
                    line_tokens_num = utils.openai_num_tokens_from_string(line)
                    logger.warning(f"当前文档内容超过{max_tokens_per_file}个token，已截断")
                # 2. 判断当前chunk是否需要继续添加token
                if current_tokens_num + line_tokens_num + len(current_chunk) > max_tokens_per_file:
                    chunks.append("\n".join(current_chunk))
                    current_chunk = []
                    current_tokens_num = 0
                current_chunk.append(line)
                current_tokens_num += line_tokens_num
            if current_chunk:
                chunks.append("\n".join(current_chunk))
            if len(chunks) > max_file_num:
                chunks = chunks[:max_file_num]
                logger.warning(f"文档超过{max_file_num}个文件，已截断")
        else:
            chunks.append("\n".join(docs))
        return chunks
    def transform_faq(self,faq_docs: List[dict], assistant_id: str,max_tokens_per_file: int, max_file_num: int) -> list:
        """
        处理faq文档
        :param faq_docs: faq文档
        :param assistant_id: gpt assistant id
        :return: faq文档的路径
        """
        if not faq_docs:
            logger.warning("本次同步的知识库文档中没有符合faq规定的相关文档，请检查")
            return None
        if max_file_num <= 0:
            logger.warning(f"{assistant_id}:文档数量超过限制,请减少文档数量")
            return None

        faq_bodies = [faq_doc["body"] for faq_doc in faq_docs]
        faq_chunks = self.divide_docs_into_chunks(docs=faq_bodies,
                                                     max_tokens_per_file=max_tokens_per_file,
                                                     max_file_num=max_file_num)

        faq_paths = []
        if len(faq_chunks) == 1:
            faq_path = os.path.join(self.tmp_dir, f"{assistant_id}/faq.md")
            faq_paths.append(faq_path)
            os.makedirs(os.path.dirname(faq_path), exist_ok=True)
            with open(faq_path, "w", encoding="utf-8") as file:
                file.write(faq_chunks[0])
            return faq_paths
        else:
            for idx, chunk in enumerate(faq_chunks):
                faq_path = os.path.join(self.tmp_dir, f"{assistant_id}/faq_{idx}.md")
                faq_paths.append(faq_path)
                os.makedirs(os.path.dirname(faq_path), exist_ok=True)
                with open(faq_path, "w", encoding="utf-8") as file:
                    file.write(chunk)
            return faq_paths
    def transform_table_docs(self, docs: List[dict], assistant_id: str, max_tokens_per_file: int, max_file_num: int) -> list:
        """
        处理表格文档
        :param docs: 表格文档
        :param assistant_id: gpt assistant id
        :return: 表格文档的路径
        """
        if not docs:
            logger.info(f"本次同步的知识库文档中, 没有表格：{assistant_id}")
            return None
        if max_file_num <= 0:
            logger.warning(f"{assistant_id}:文档数量超过限制,请减少文档数量")
            return None

        htm_docs = []
        # 将表格文档转换为html格式
        for doc in docs:
            htm = f"<h1>{doc['title']}</h1>\n"
            sheets = json.loads(doc['body_sheet'])['data']
            for sheet in sheets:
                table = sheet['table']
                df = pd.DataFrame(table)
                utils.clear_pd_nan(df)
                htm = htm + f"<h2>{sheet['name']}</<h2>\n" + df.to_html(index=False) + "\n"
            htm_docs.append(htm)

        # html_content = "\n".join(htm_docs)

        table_chunks = self.divide_docs_into_chunks(docs=htm_docs,
                                                     max_tokens_per_file=max_tokens_per_file,
                                                     max_file_num=max_file_num)

        table_paths = []
        if len(table_chunks) == 1:
            table_path = os.path.join(self.tmp_dir, f"{assistant_id}/table.html")
            table_paths.append(table_path)
            os.makedirs(os.path.dirname(table_path), exist_ok=True)
            with open(table_path, "w", encoding="utf-8") as file:
                file.write(table_chunks[0])
            return table_paths
        else:
            for idx, chunk in enumerate(table_chunks):
                table_path = os.path.join(self.tmp_dir, f"{assistant_id}/table_{idx}.html")
                table_paths.append(table_path)
                os.makedirs(os.path.dirname(table_path), exist_ok=True)
                with open(table_path, "w", encoding="utf-8") as file:
                    file.write(chunk)
            return table_paths
    def transform_docs(self, docs, assistant_id, max_file_num: int):
        if len(docs) == 0:
            logger.warning("语雀文档中没有符合规定的相关文档，请检查")
            return None
        if max_file_num <= 0:
            logger.warning(f"{assistant_id}:文档数量超过限制,请减少文档数量")
            return None

        base_path = os.path.join(self.tmp_dir, f"{assistant_id}")
        os.makedirs(os.path.dirname(base_path), exist_ok=True)

        # 将文档内容分配到多个文件中，以应对gpt assistant的文件上限
        operated_files = self.distribute_docs(docs, max_file_num,base_path)

        file_path = [os.path.join(base_path, f.name) for f in operated_files]

        return file_path
    def distribute_docs(self, docs: List[dict], max_file_num: int, base_path:str ="./tmp"):
        """
        将文件内容平均分配到FILE_NUM_LIMIT个文件中
        :param docs:
        :param base_path: 保存结果的路径
        :return:
        """
        act_num_more_less = False
        # limit = ASSISTANT_FILE_NUM_LIMIT
        limit = max_file_num
        if len(docs) < limit:
            # 语雀文档实际数量小于assistant的文件上限数，则无需分配，直接按顺序存储即可
            logger.info("语雀实际文档数小于assistant的文件上限数，一个语雀文档对应一个assistant文件即可")
            limit = len(docs)
            act_num_more_less = True

        file_buckets = []
        if act_num_more_less:
            for index in range(limit):
                # 语雀实际文档数小于assistant的文件上限数，一个语雀文档对应一个assistant文件即可
                doc = docs[index]
                file_path = os.path.join(base_path, str(index + 1) + ".md")
                with open(file_path, "w", encoding="utf-8") as file:
                    body = self.transform_md_body(doc["body"], doc["title"])
                    file.write(body)
                    file_buckets.append(file)
        else:
            for index in range(limit):
                # 初始化ASSISTANT_FILE_NUM_LIMIT个文件
                file_path = os.path.join(base_path, str(index + 1) + ".md.tmp")
                with open(file_path, 'w', encoding="utf-8") as file:
                    file.write("")
                    file_buckets.append(file)

            word_count_buckets = [[] for _ in range(limit)]
            doc_buckets = [[] for _ in range(limit)]
            # 对输入文件数组按word_count进行排序（从大到小）
            sorted_docs = sorted(docs, key=lambda x: x["word_count"], reverse=True)
            # 对于排序后的每个元素，找到当前总和最小的桶，并将其放入
            for doc in sorted_docs:
                # 计算每个文件的字数总和
                word_count_bucket_sums = [sum(count_bucket) for count_bucket in word_count_buckets]

                # 找到总和最小的文件的索引
                min_bucket_index = word_count_bucket_sums.index(min(word_count_bucket_sums))

                word_count_buckets[min_bucket_index].append(doc["word_count"])
                doc_buckets[min_bucket_index].append(doc)
                file_path = os.path.join(base_path, file_buckets[min_bucket_index].name)
                with open(file_path, "a", encoding="utf-8") as file:
                    body = self.transform_md_body(doc["body"], doc["title"])
                    file.write(body)
            self.add_index_in_doc_start(file_buckets, doc_buckets, base_path)

        return file_buckets
    def add_index_in_doc_start(self, file_buckets, doc_buckets, base_path="./tmp"):
        """
        给每个文件的开头添加索引
        """
        chunk_size = 1024 * 1024
        for index in range(len(file_buckets)):
            file_path = os.path.join(base_path, file_buckets[index].name)
            with open(file_path, "r", encoding="utf-8") as ori_file, \
                    open(os.path.join(base_path, ori_file.name[:-len(".tmp")]), "w", encoding="utf-8") as file:
                # file.write("<b>文件索引：</b><br>")
                # word_count_sum = 0
                # for doc in doc_buckets[index]:
                #     file.write(f"《{doc['title']} 》开始位置（字数）：{word_count_sum} <br>")
                #     extra_word_count = len(SINGLE_DOC_END.format(doc["title"], doc["word_count"]))
                #     word_count_sum += doc["word_count"] + extra_word_count
                # file.write("<b>===================================索引分割============================================</b>")
                # 分块复制文件
                while True:
                    chunk = ori_file.read(chunk_size)
                    if not chunk:
                        break
                    file.write(chunk)
                file_buckets[index] = file
            # 删除旧.tmp结尾文件
            os.remove(os.path.join(base_path, file_buckets[index].name) + ".tmp")
    def transform_md_body(self,body, title):
        body = re.sub("<a name=\".*\"></a>", "", body)  # 去除语雀导出的<a>标签
        body = re.sub("\x00", "", body)  # 去除不可见字符\x00
        body = re.sub("\x05", "", body)  # 去除不可见字符\x05
        body = re.sub(r'\<br \/\>!\[image.png\]', "\n![image.png]", body)  # 去除语雀导出的图片后紧跟的<br \>标签
        body = re.sub(r'\)\<br \/\>', ")\n", body)  # 去除语雀导出的图片后紧跟的<br \>标签
        body = f"# {title} \n" + body
        return body

