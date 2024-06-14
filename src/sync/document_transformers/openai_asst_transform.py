"""
GPT Assistant Transfomer模块，提供文档清洗、文档转换功能
"""

import json
import re
import os
from typing import List

import pandas as pd
from src.utils import data_process
import src.utils.common_utils as utils
from src.utils.logger import logger

class OpenAIAsstTransformer:
    """适用于openai assistant/ azure openai assistant 或者其他存在assistant_id且只需要对文档简单处理的助手"""
    # 限制文件数量：10000
    # 限制文件大小：512MB
    # 限制文件token数量：5000000
    def __init__(self, file_num_limit=10000, file_token_limit=5000000):
        if file_num_limit is None:
            file_num_limit = 10000
        if file_token_limit is None:
            file_token_limit = 5000000
        self.FILE_NUM_LIMIT = file_num_limit
        self.FILE_TOKEN_LIMIT = file_token_limit
        self.tmp_dir = os.path.join(os.path.dirname(__file__), "../../../openai_tmp")
    def __call__(self,yuque_docs: List[dict],assistant_id: str):
        max_file_num = self.FILE_NUM_LIMIT
        # 1、先清空临时文件夹下的文件
        base_path = os.path.join(self.tmp_dir, str(assistant_id))
        if os.path.exists(base_path):
            for file in os.listdir(base_path):
                file_path = os.path.join(base_path, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)
        # 2、将文档拆分为普通文档、表格文档、faq文档
        docs, table_docs, faq_docs = self.split_docs(yuque_docs)
        # 3、保存faq文档
        faq_paths = self.transform_faq(faq_docs, assistant_id, self.FILE_TOKEN_LIMIT)
        max_file_num -= len(faq_paths)
        table_docs_paths = self.transform_table_docs(table_docs, assistant_id, self.FILE_TOKEN_LIMIT, max_file_num)
        max_file_num -= len(table_docs_paths) if table_docs_paths is not None else 0
        docs_paths = self.transform_docs(docs, assistant_id, self.FILE_TOKEN_LIMIT, max_file_num)
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
    def limit_doc_token(self, docs: dict, max_tokens_per_file: int):
        """
        限制文档内容的token数量
        :param docs: 待分配的文档
        :param max_tokens_per_file: 每个文件的最大token数
        :return:
        """
        for doc in docs:
            doc_body = doc["body"]
            current_tokens_num = utils.openai_num_tokens_from_string(doc_body)
            if current_tokens_num > max_tokens_per_file:
                doc_body = utils.openai_truncate_string(doc_body, max_tokens_per_file)
                logger.warning(f"文档 '{doc['title']}' 的内容超过{max_tokens_per_file}个token，已截断")
                doc["body"] = doc_body
        return docs
    def transform_faq(self,faq_docs: List[dict], assistant_id: str, max_tokens_per_file: int) -> list:
        """
        处理faq文档
        :param faq_docs: faq文档
        :param assistant_id: gpt assistant id
        :return: faq文档的路径
        """
        faq_paths = []
        if not faq_docs:
            logger.warning("本次同步的知识库文档中没有符合faq规定的相关文档，请检查")
            return faq_paths
        new_faq_docs = []
        for doc in faq_docs:
            if doc["published_at"] is None and not doc["body"].strip():
                continue
            body = self.transform_md_body(doc["body"], doc["title"])
            doc["body"] = body
            new_faq_docs.append(doc)
        new_faq_docs = self.limit_doc_token(docs=new_faq_docs,max_tokens_per_file=max_tokens_per_file)

        if len(new_faq_docs) == 1:
            faq_path = os.path.join(self.tmp_dir, f"{assistant_id}/faq.md")
            faq_paths.append(faq_path)
            os.makedirs(os.path.dirname(faq_path), exist_ok=True)
            with open(faq_path, "w", encoding="utf-8") as file:
                file.write(new_faq_docs[0]["body"])
            return faq_paths

        for idx, doc in enumerate(new_faq_docs):
            faq_path = os.path.join(self.tmp_dir, f"{assistant_id}/faq_{idx}.md")
            faq_paths.append(faq_path)
            os.makedirs(os.path.dirname(faq_path), exist_ok=True)
            with open(faq_path, "w", encoding="utf-8") as file:
                file.write(doc["body"])
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
            return []
        if max_file_num <= 0:
            logger.warning(f"{assistant_id}:文档数量超过限制,请减少文档数量")
            return []

        htm_docs = []
        # 将表格文档转换为html格式
        for doc in docs:
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
                    htm = f"<h1>{doc['title']}</h1>\n<h2>{sheet['name']}</<h2>\n" + df.to_html(index=False)
                    file_name = data_process.process_file_name(doc["title"]) + "_" + data_process.process_file_name(sheet["name"])
                    htm_docs.append({"title": file_name,"body": htm})
                except Exception as e:
                    logger.error(f"表格文档[{doc['title']} - {sheet['name']}]转换失败：{e}.{traceback.format_exc()}")

        htm_docs = self.limit_doc_token(docs=htm_docs,max_tokens_per_file=max_tokens_per_file)

        base_path = os.path.join(self.tmp_dir, f"{assistant_id}")
        os.makedirs(base_path, exist_ok=True)

        # 将文档内容分配到多个文件中，以应对gpt assistant的文件上限
        operated_files = self.distribute_docs(htm_docs, max_file_num, base_path, "html")

        table_paths = [os.path.join(base_path, f.name) for f in operated_files]
        return table_paths
    def transform_docs(self, docs, assistant_id, max_tokens_per_file: int, max_file_num: int):
        if len(docs) == 0:
            logger.warning(f"[asst_id={assistant_id}]：语雀文档中没有符合规定的相关文档，请检查")
            return []
        if max_file_num <= 0:
            logger.warning(f"[asst_id={assistant_id}]：文档数量超过限制,请减少文档数量后重新同步")
            return []
        new_docs = []
        for doc in docs:
            if doc["published_at"] is None and not doc["body"].strip():
                continue
            body = self.transform_md_body(doc["body"], doc["title"])
            doc["body"] = body
            new_docs.append(doc)
        new_docs = self.limit_doc_token(docs=new_docs, max_tokens_per_file=max_tokens_per_file)


        base_path = os.path.join(self.tmp_dir, f"{assistant_id}")
        os.makedirs(base_path, exist_ok=True)

        # 将文档内容分配到多个文件中，以应对gpt assistant的文件上限
        operated_files = self.distribute_docs(new_docs, max_file_num,base_path,"md")

        file_paths = [os.path.join(base_path, f.name) for f in operated_files]

        return file_paths
    def distribute_docs(self, docs: List[dict], max_file_num: int, base_path:str ="./tmp", suffix="md"):
        """
        将文件内容平均分配到FILE_NUM_LIMIT个文件中
        :param docs:
        :param base_path: 保存结果的路径
        :return:
        """
        act_num_more_less = False # 语雀文档实际数量是否小于assistant的文件上限数
        # limit = ASSISTANT_FILE_NUM_LIMIT
        limit = max_file_num
        if len(docs) < limit:
            # 语雀文档实际数量小于assistant的文件上限数，则无需分配，直接按顺序存储即可
            logger.info("语雀实际文档数小于assistant的文件上限数，一个语雀文档对应一个assistant文件即可")
            limit = len(docs)
            act_num_more_less = True

        file_buckets = []
        if act_num_more_less:
            exist_file_names = []
            for index in range(limit):
                # 语雀实际文档数小于assistant的文件上限数，一个语雀文档对应一个assistant文件即可
                doc = docs[index]
                file_name = data_process.process_file_name(doc["title"])
                while file_name in exist_file_names:
                    file_name = f"{file_name}_{index}"
                file_path = os.path.join(base_path, file_name + "." +suffix)
                exist_file_names.append(file_name)
                with open(file_path, "w", encoding="utf-8") as file:
                    file.write(doc["body"])
                    file_buckets.append(file)
        else:
            for index in range(limit):
                # 初始化ASSISTANT_FILE_NUM_LIMIT个文件
                file_path = os.path.join(base_path, str(index + 1) + f".{suffix}.tmp")
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
                    file.write(doc["body"])
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

    def increase_level(self, match):
        # 将标题级别升高一级
        return '#' + match.group(0)

