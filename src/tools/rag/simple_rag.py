import time
import json
import re
from enum import Enum
from typing import List
from functools import cached_property

import traceback
import openai
import pypinyin
from openai import OpenAI
from openai import AzureOpenAI
from openai.types.beta.threads import Run
from langchain.docstore.document import Document

from src.tools.rag.store import DocStore
from src.tools.rag.prompt import SIMPLE_FAQ_PROMPT, SIMPLE_DOC_PROMPT
from src.sync.document_transformers.simple_rag_transform import DocType, MetaKey
from src.utils.logger import logger
from src.utils.data_process import process_topic_name
from src.tools.rag.base_rag import BaseRAGTool, RAGLLMType, RAGEmbeddingType, RAGType


class SimpleRAGTool(BaseRAGTool):
    def __init__(self, rag_config: dict, topic: str):
        super(SimpleRAGTool, self).__init__(rag_config)
        self.rag_type = RAGType.SIMPLE_RAG
        self._initialize_configs()
        self._setup_llm()
        self._initialize_doc_store(topic, rag_config)

    @cached_property
    def _faq_prompt(self) -> str:
        return SIMPLE_FAQ_PROMPT.replace("{topic}", self.topic)

    @cached_property
    def _doc_prompt(self) -> str:
        return SIMPLE_DOC_PROMPT.replace("{topic}", self.topic)

    def invoke_functions(self, query: str):
        """
        :param query: 问题
        :return: the result of the function
        """
        output_result = {}
        # 1. 检索文档
        faq_chunks, doc_chunks = self.doc_store.search(query=query, doc_topk=self.doc_topk, faq_topk=self.faq_topk)
        if not faq_chunks and not doc_chunks:
            logger.info(f"文档库和FAQ库未检索到可用文档和FAQ")
            output_result["result"] = "未找到答案"
            return output_result
        if faq_chunks:
            faq_answer_result = self._process_faq(faq_chunks, query)
            if (faq_answer_result.get("is_answer_found", False) and
                    faq_answer_result.get("answer_text", "未找到答案").strip() != "未找到答案"):
                output_result["result"] = faq_answer_result["answer_text"]
                return output_result
        if not doc_chunks:
            logger.info(f"文档库未检索到可用文档")
            output_result["result"] = "未找到答案"
            return output_result
        output_result["result"] = self._process_documents(doc_chunks, query)
        return output_result

    def _process_faq(self, faq_chunks: List[Document], query: str):
        faq_content = "\n".join([f"{idx+1}. {faq_chunk.page_content}" for idx, faq_chunk in enumerate(faq_chunks)])
        faq_prompt = self._faq_prompt.replace("{content}", faq_content)
        logger.debug(f"faq_prompt: {faq_prompt}".encode().decode('unicode-escape'))
        try:
            llm_response = self._llm_answer(system_prompt=faq_prompt, query=query)
            faq_answer_result = self._json_parse(llm_response)
            logger.debug(f"FAQ问答llm结果: {llm_response}")
        except Exception as e:
            logger.info(f"FAQ问答遇到错误： {e}")
            faq_answer_result = {"is_answer_found": False, "answer_text": "未找到答案"}
        return faq_answer_result

    def _process_documents(self, doc_chunks: List[Document], query: str):
        doc_content = self._format_doc_content(doc_chunks)
        doc_prompt = self._doc_prompt.replace("{content}", doc_content)
        logger.debug(f"doc_prompt: {doc_prompt}".encode().decode('unicode-escape'))
        try:
            llm_response = self._llm_answer(system_prompt=doc_prompt, query=query)
            logger.debug(f"文档问答llm结果: {llm_response}")
        except ValueError as e:
            doc_answer_result = {"is_answer_found": False,
                                 "answer_text": "大模型调用超时，请稍后再试"}
        else:
            try:
                doc_answer_result = self._json_parse(llm_response)
            except ValueError as e:
                doc_answer_result = {"is_answer_found": False,
                                     "answer_text": llm_response}

        output = doc_answer_result.get("answer_text", "未找到答案")
        if doc_answer_result.get("document", None):
            try:
                for idx, doc_ins in enumerate(doc_answer_result["document"]):
                    output += f"\n[{idx + 1}] {doc_ins['title']}: {doc_ins['url']}"
            except Exception as e:
                logger.error(f"document信息解析错误: {e}\n{doc_answer_result['document']}")
        return output

    # @retry(wait=wait_random_exponential(multiplier=1, max=40), stop=stop_after_attempt(3))
    def _llm_answer(self, system_prompt: str, query: str) -> str:
        """
        调用大模型
        :param system_prompt: 系统提示
        :param query: 用户问题
        :return: 大模型返回结果
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ],
                **self.llm_kwargs
            )
            message_content = response.choices[0].message.content
            logger.debug(f"Input tokens: {response.usage.prompt_tokens}")
            logger.debug(f"Output tokens: {response.usage.completion_tokens}")
            return message_content
        except Exception as e:
            logger.error(f"调用大模型错误: {e}")
            raise ValueError("大模型调用错误")

    def _json_parse(self, result: str) -> dict:
        """
        解析json
        :param result: 结果
        """
        try:
            return json.loads(result)
        except:
            try:
                start_index = result.index("{")
                end_index = result.rindex("}") + 1
                return json.loads(result[start_index:end_index])
            except Exception as e:
                logger.error(f"解析json出错: {e}\n {result}")
                raise ValueError(f"解析json出错")

    def _format_doc_content(self, doc_chunks: List[Document]):
        """
        文档内容规范化
        :param doc_chunks: 文档块
        :return: 规范化的文档内容
        """
        doc_content = []
        for doc_chunk in doc_chunks:
            title = doc_chunk.metadata["title"]
            if doc_chunk.metadata["doc_type"] == DocType.TABLE.value:
                title += f"-{doc_chunk.metadata['sheet_name']}"
            doc_url = doc_chunk.metadata["doc_url"]
            chunk_info = {"title": title, "doc_url": doc_url, "content_fragment": doc_chunk.page_content}
            doc_content.append(json.dumps(chunk_info))
        return "\n".join(doc_content)


    def _initialize_configs(self):
        """
        初始化额外配置
        """
        self.faq_topk = self.docdb_config["faq_top_k"]
        self.doc_topk = self.docdb_config["doc_top_k"]

    def _setup_llm(self):
        """
        设置大模型
        """
        llm_option = self.chat_config["llm_option"]
        llm_config = self.chat_config["llm_config"][llm_option]
        if llm_option == RAGLLMType.OPENAI:
            self.client = OpenAI(api_key=llm_config["openai_api_key"])
            self.model_name = llm_config["model_name"]
            self.llm_kwargs = llm_config["llm_kwargs"]
        elif llm_option == RAGLLMType.AZURE:
            self.client = AzureOpenAI(
                api_key=llm_config["azure_openai_api_key"],
                api_version=llm_config["openai_api_version"],
                azure_endpoint=llm_config["azure_openai_endpoint"]
            )
            self.model_name = llm_config["model_name"]
            self.llm_kwargs = llm_config["llm_kwargs"]
        else:
            raise ValueError(f"Unsupported RAG LLM option: {llm_option}")

    def _initialize_doc_store(self, topic: str, rag_config: dict):
        """
        初始化文档库
        """
        attributes = [metakey.value for metakey in MetaKey]
        self.topic = topic
        self.project_name = process_topic_name(f"{topic}_simpledocdb")
        self.doc_store = DocStore(project_name=self.project_name, rag_config=rag_config, attributes=attributes)

