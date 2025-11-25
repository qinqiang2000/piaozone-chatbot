"""
GPT Assistant Transfomer模块，提供文档清洗、文档转换功能
"""

import json
import re
import os
from typing import List

import pandas as pd
import traceback
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
    def __call__(self,yuque_docs: List[dict],assistant_id: str, base_url: str, file_name_prefix: str=""):
        max_file_num = self.FILE_NUM_LIMIT
        # 1、将文档拆分为普通文档、表格文档、faq文档
        docs, table_docs, faq_docs = self.split_docs(yuque_docs)
        # 2、保存faq文档
        faq_paths = self.transform_faq(faq_docs, assistant_id, base_url,self.FILE_TOKEN_LIMIT, max_file_num,file_name_prefix)
        max_file_num -= len(faq_paths)
        table_docs_paths = self.transform_table_docs(table_docs, assistant_id, base_url,self.FILE_TOKEN_LIMIT, max_file_num,file_name_prefix)
        max_file_num -= len(table_docs_paths) if table_docs_paths is not None else 0
        docs_paths = self.transform_docs(docs, assistant_id, base_url,self.FILE_TOKEN_LIMIT, max_file_num,file_name_prefix)
        if faq_paths:
            docs_paths.extend(faq_paths)
        if table_docs_paths:
            docs_paths.extend(table_docs_paths)
        
        # ========== 保存按分类组织的文档副本（测试用，可独立删除） ==========
        self._save_category_copy(yuque_docs, assistant_id, base_url, file_name_prefix)
        # ========== 分类副本保存结束 ==========
        
        return docs_paths
    def empty_cache(self, assistant_id: str):
        """清空临时文件夹下的文件"""
        base_path = os.path.join(self.tmp_dir, str(assistant_id))
        if os.path.exists(base_path):
            for file in os.listdir(base_path):
                file_path = os.path.join(base_path, file)
                if os.path.isfile(file_path):
                    os.remove(file_path)

    def split_docs(self, yq_docs: List[dict]):
        """
        拆分文档为普通文档、表格文档、faq文档
        :param yq_docs: 语雀文档
        """
        docs = []
        table_docs = []
        faq_docs = []
        for doc in yq_docs:
            try:
                if (doc["format"] == "markdown" or doc["format"] == "lake") \
                        and "faq" in doc["title"].lower() and doc["body"]:
                    faq_docs.append(doc)
                elif doc["format"] == "lake" and "body" in doc and doc["body"]:
                    docs.append(doc)
                elif doc["format"] == "lakesheet" and "body_sheet" in doc and doc["body_sheet"]:
                    table_docs.append(doc)
            except Exception as e:
                logger.error(f"文档 '{doc['slug']}'解析失败：{e}: {traceback.format_exc()}")
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
    def transform_faq(self,faq_docs: List[dict], assistant_id: str, base_url:str,
                      max_tokens_per_file: int, max_file_num: int, file_name_prefix: str="") -> list:
        """
        处理faq文档
        :param faq_docs: faq文档
        :param assistant_id: gpt assistant id
        :return: faq文档的路径
        """
        faq_paths = []
        if not faq_docs:
            logger.warning(f"[asst_id={assistant_id}]：本次同步的知识库文档中没有符合faq规定的相关文档，请检查")
            return faq_paths
        new_faq_docs = []
        for doc in faq_docs:
            if doc["published_at"] is None and not doc["body"].strip():
                continue
            body = self.transform_md_body(doc["body"], doc["title"])
            doc["body"] = body
            doc['url'] = f"{base_url}/{doc['slug']}?singleDoc"
            new_faq_docs.append(doc)
        new_faq_docs = self.limit_doc_token(docs=new_faq_docs,max_tokens_per_file=max_tokens_per_file)

        base_path = os.path.join(self.tmp_dir, f"{assistant_id}")
        os.makedirs(base_path, exist_ok=True)

        # 将文档内容分配到多个文件中，以应对gpt assistant的文件上限

        faq_paths = self.distribute_docs(new_faq_docs, max_file_num, base_path, "md",file_name_prefix)

        return faq_paths
    def transform_table_docs(self, docs: List[dict], assistant_id: str, base_url: str,
                             max_tokens_per_file: int, max_file_num: int, file_name_prefix: str="") -> list:
        """
        处理表格文档
        :param docs: 表格文档
        :param assistant_id: gpt assistant id
        :return: 表格文档的路径
        """
        if not docs:
            logger.info(f"[asst_id={assistant_id}]：本次同步的知识库文档中, 没有表格")
            return []
        if max_file_num <= 0:
            logger.warning(f"[asst_id={assistant_id}]：文档数量超过限制,请减少文档数量")
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
                    sheet_id = sheet.get('id', "")
                    df = pd.DataFrame(table)
                    data_process.clear_pd_nan(df)
                    htm = f"<h1>{doc['title']}</h1>\n<h2>{sheet['name']}</<h2>\n" + df.to_html(index=False)
                    file_name = data_process.process_file_name(doc["title"]) + "_" + data_process.process_file_name(sheet["name"])
                    htm_docs.append({"title": file_name,"body": htm,"url":f"{base_url}/{doc['slug']}?singleDoc#{sheet_id}"})
                except Exception as e:
                    logger.error(f"[asst_id={assistant_id}]：表格文档[{doc['title']} - {sheet['name']}]转换失败：{e}.{traceback.format_exc()}")

        htm_docs = self.limit_doc_token(docs=htm_docs,max_tokens_per_file=max_tokens_per_file)

        base_path = os.path.join(self.tmp_dir, f"{assistant_id}")
        os.makedirs(base_path, exist_ok=True)

        # 将文档内容分配到多个文件中，以应对gpt assistant的文件上限
        table_paths = self.distribute_docs(htm_docs, max_file_num, base_path, "html",file_name_prefix)
        return table_paths
    def transform_docs(self, docs, assistant_id, base_url:str,max_tokens_per_file: int,
                       max_file_num: int, file_name_prefix: str="") -> list:
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
            doc['url'] = f"{base_url}/{doc['slug']}?singleDoc"
            new_docs.append(doc)
        new_docs = self.limit_doc_token(docs=new_docs, max_tokens_per_file=max_tokens_per_file)


        base_path = os.path.join(self.tmp_dir, f"{assistant_id}")
        os.makedirs(base_path, exist_ok=True)

        # 将文档内容分配到多个文件中，以应对gpt assistant的文件上限

        file_paths = self.distribute_docs(new_docs, max_file_num,base_path,"md",file_name_prefix)

        return file_paths
    def distribute_docs(self, docs: List[dict], max_file_num: int, base_path:str ="./tmp",
                        suffix="md", file_name_prefix: str=""):
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
        results = {}
        if act_num_more_less:
            exist_file_names = []
            for index in range(limit):
                # 语雀实际文档数小于assistant的文件上限数，一个语雀文档对应一个assistant文件即可
                doc = docs[index]
                file_name = data_process.process_file_name(file_name_prefix+"-"+doc["title"] if file_name_prefix else doc["title"])
                while file_name in exist_file_names:
                    file_name = f"{file_name}_{index}"
                file_path = os.path.join(base_path, file_name + "." +suffix)
                exist_file_names.append(file_name)
                with open(file_path, "w", encoding="utf-8") as file:
                    file.write(doc["body"])
                    file_buckets.append(file)
                    url = doc.get("url", "")
                    if file_path in results:
                        results[file_path]["url"] += ',' + url
                    else:
                        results[file_path] = {"file_path": file_path, "url": url}

        else:
            for index in range(limit):
                # 初始化ASSISTANT_FILE_NUM_LIMIT个文件
                file_path = os.path.join(base_path, f"{file_name_prefix}-{index + 1}.{suffix}" if file_name_prefix else f"{index + 1}.{suffix}")
                with open(file_path, 'w', encoding="utf-8") as file:
                    file.write("")
                    file_buckets.append(file)

            word_count_buckets = [[] for _ in range(limit)]
            doc_buckets = [[] for _ in range(limit)]
            for doc in docs:
                doc["word_count"] = len(doc["body"])
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
                    url = doc.get("url", "")
                    if file_path in results:
                        results[file_path]["url"] += ',' + url
                    else:
                        results[file_path] = {"file_path": file_path, "url": url}
            # self.add_index_in_doc_start(file_buckets, doc_buckets, base_path)

        return [(ins['url'], ins['file_path']) for ins in results.values()]
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
    
    # ========== 以下为分类副本保存功能（测试用，可独立删除） ==========
    def _save_category_copy(self, yuque_docs: List[dict], assistant_id: str, base_url: str, category_name: str):
        """
        保存按语雀目录结构组织的文档副本（仅用于测试调试）
        :param yuque_docs: 语雀文档列表
        :param assistant_id: 助手ID
        :param base_url: 基础URL
        :param category_name: 分类名称（即toc_title）
        """
        if not category_name:
            logger.debug(f"[asst_id={assistant_id}]：分类名称为空，跳过分类副本保存")
            return
        
        # 创建分类副本目录: openai_tmp/{assistant_id}/category/{category_name}/
        category_base_path = os.path.join(self.tmp_dir, str(assistant_id), "category", category_name)
        os.makedirs(category_base_path, exist_ok=True)
        
        saved_count = 0
        for doc in yuque_docs:
            try:
                
                # 跳过未发布或空文档
                if doc.get("published_at") is None:
                    continue
                
                doc_format = doc.get("format", "")
                doc_title = doc.get("title", "untitled")
                
                # 处理普通文档（lake格式）
                if doc_format == "lake" and "body" in doc and doc["body"]:
                    # ========== 调试功能：使用多级目录路径（可独立删除） ==========
                    debug_path_segments = doc.get("_debug_directory_path", [])
                    if debug_path_segments:
                        # 检查是否第一个路径段与category_name重复，如果重复则跳过
                        if debug_path_segments and debug_path_segments[0] == category_name:
                            # 跳过重复的顶级目录
                            actual_path_segments = debug_path_segments[1:] if len(debug_path_segments) > 1 else []
                        else:
                            actual_path_segments = debug_path_segments
                        
                        if actual_path_segments:
                            # 使用去重后的目录路径
                            sub_dir_path = os.path.join(category_base_path, *actual_path_segments)
                            os.makedirs(sub_dir_path, exist_ok=True)
                            file_path = os.path.join(sub_dir_path, data_process.process_file_name(doc_title) + ".md")
                            path_info = f"{category_name}/{'/'.join(actual_path_segments)}"
                        else:
                            # 只有顶级目录，直接使用category_base_path
                            file_path = os.path.join(category_base_path, data_process.process_file_name(doc_title) + ".md")
                            path_info = category_name
                    else:
                        # 回退到原来的逻辑
                        file_path = os.path.join(category_base_path, data_process.process_file_name(doc_title) + ".md")
                        path_info = category_name
                    # ========== 调试功能结束 ==========
                    
                    body = self.transform_md_body(doc["body"], doc_title)
                    file_name = data_process.process_file_name(doc_title) + ".md"
                    
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(body)
                    saved_count += 1
                    logger.debug(f"[asst_id={assistant_id}]：保存分类副本 [{path_info}/{file_name}]")
                
                # 处理FAQ文档（markdown格式）
                elif (doc_format == "markdown" or doc_format == "lake") and "faq" in doc_title.lower() and doc.get("body"):
                    # ========== 调试功能：使用多级目录路径（可独立删除） ==========
                    debug_path_segments = doc.get("_debug_directory_path", [])
                    if debug_path_segments:
                        # 检查是否第一个路径段与category_name重复，如果重复则跳过
                        if debug_path_segments and debug_path_segments[0] == category_name:
                            # 跳过重复的顶级目录
                            actual_path_segments = debug_path_segments[1:] if len(debug_path_segments) > 1 else []
                        else:
                            actual_path_segments = debug_path_segments
                        
                        if actual_path_segments:
                            # 使用去重后的目录路径
                            sub_dir_path = os.path.join(category_base_path, *actual_path_segments)
                            os.makedirs(sub_dir_path, exist_ok=True)
                            file_path = os.path.join(sub_dir_path, data_process.process_file_name(doc_title) + ".md")
                            path_info = f"{category_name}/{'/'.join(actual_path_segments)}"
                        else:
                            # 只有顶级目录，直接使用category_base_path
                            file_path = os.path.join(category_base_path, data_process.process_file_name(doc_title) + ".md")
                            path_info = category_name
                    else:
                        # 回退到原来的逻辑
                        file_path = os.path.join(category_base_path, data_process.process_file_name(doc_title) + ".md")
                        path_info = category_name
                    # ========== 调试功能结束 ==========
                    
                    body = self.transform_md_body(doc["body"], doc_title)
                    file_name = data_process.process_file_name(doc_title) + ".md"
                    
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(body)
                    saved_count += 1
                    logger.debug(f"[asst_id={assistant_id}]：保存分类副本 [{path_info}/{file_name}]")
                
                # 处理表格文档（lakesheet格式）
                elif doc_format == "lakesheet" and "body_sheet" in doc and doc["body_sheet"]:
                    # ========== 调试功能：使用多级目录路径（可独立删除） ==========
                    debug_path_segments = doc.get("_debug_directory_path", [])
                    if debug_path_segments:
                        # 检查是否第一个路径段与category_name重复，如果重复则跳过
                        if debug_path_segments and debug_path_segments[0] == category_name:
                            # 跳过重复的顶级目录
                            actual_path_segments = debug_path_segments[1:] if len(debug_path_segments) > 1 else []
                        else:
                            actual_path_segments = debug_path_segments
                        
                        if actual_path_segments:
                            # 使用去重后的目录路径
                            sub_dir_path = os.path.join(category_base_path, *actual_path_segments)
                            os.makedirs(sub_dir_path, exist_ok=True)
                            path_info = f"{category_name}/{'/'.join(actual_path_segments)}"
                        else:
                            # 只有顶级目录，直接使用category_base_path
                            sub_dir_path = category_base_path
                            path_info = category_name
                    else:
                        # 回退到原来的逻辑
                        sub_dir_path = category_base_path
                        path_info = category_name
                    # ========== 调试功能结束 ==========
                    
                    sheets = json.loads(doc['body_sheet'])['data']
                    for sheet in sheets:
                        try:
                            table = sheet.get('table')
                            if not table or table == [['']]:
                                continue
                            
                            df = pd.DataFrame(table)
                            data_process.clear_pd_nan(df)
                            htm = f"<h1>{doc_title}</h1>\n<h2>{sheet['name']}</h2>\n" + df.to_html(index=False)
                            
                            sheet_name = data_process.process_file_name(sheet['name'])
                            file_name = data_process.process_file_name(doc_title) + "_" + sheet_name + ".html"
                            file_path = os.path.join(sub_dir_path, file_name)
                            
                            with open(file_path, "w", encoding="utf-8") as f:
                                f.write(htm)
                            saved_count += 1
                            logger.debug(f"[asst_id={assistant_id}]：保存分类副本 [{path_info}/{file_name}]")
                        except Exception as e:
                            logger.debug(f"[asst_id={assistant_id}]：表格文档[{doc_title} - {sheet['name']}]分类副本保存失败：{e}")
            
            except Exception as e:
                logger.debug(f"[asst_id={assistant_id}]：文档[{doc.get('title', 'unknown')}]分类副本保存失败：{e}")
        
        logger.debug(f"[asst_id={assistant_id}]：分类[{category_name}]副本保存完成，共保存 {saved_count} 个文件")
    # ========== 分类副本保存功能结束 ==========

