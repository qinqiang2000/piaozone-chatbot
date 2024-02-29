"""
============================
# -*- coding: utf-8 -*-
# @Time    : 2024/1/15 10:00
# @Author  : LinLimin
# @Desc    : 语雀reader模块，提供读取语雀知识库文档的能力。语雀知识库文档的结构如下：
#           语雀空间
#           |---知识库1
#           |   |---专题库1（每个专题知识库负责人负责）
#           |   |   |--- 政策相关文档1
#           |   |   |--- 操作指引文档2
#           |   |   |--- 常见问题文档3
#           |   |   |--- ...
===========================
"""
import json
import requests
from typing import List

from src.utils.logger import logger

class YQReader:
    def __init__(self, yuque_base_url, yuque_namespace, yuque_auth_token, yuque_request_agent, yuque_repos):
        self.YUQUE_BASE_URL = yuque_base_url
        self.YUQUE_NAMESPACE = yuque_namespace
        self.YUQUE_AUTH_TOKEN = yuque_auth_token
        self.YUQUE_REQUEST_AGENT = yuque_request_agent
        self.repo2tocs_map = {}
        self.init_tocs_list(yuque_repos)
    def init_tocs_list(self,repos:List[str]):
        """
        初始化知识库的目录树
        :param repo: 知识库的唯一标识
        :return:
        """
        for repo in repos:
            toc_list = self.list_yuque_toc(repo)
            self.repo2tocs_map[repo] = toc_list

    def get_docs_for_topic_title(self,repo, toc_title):
        """
        基于知识库标识以及专题库名称，获取指定的语雀专题库下的所有文档
        :param repo: 知识库的唯一标识
        :param toc_title: 目录title,对应知识库的专题库
        :return:
        """
        # 更新缓存的知识库的所有目录
        self.repo2tocs_map[repo] = self.list_yuque_toc(repo)
        # 1、根据目录title获取对应的uuid
        toc_uuid = self._get_uuid_by_title(repo, toc_title)

        # 2、获取专题库目录下的所有文档
        #2.1 获取专题库目录下的一级目录
        tocs = self._get_tocs_from_parent(repo, toc_uuid)
        #2.2 获取一级目录下的所有文档
        docs = self._get_doc_from_tocs(tocs)
        return docs

    def get_topic_title_for_single_doc(self,repo, doc_id, action):
        """
        基于知识库标识以及文档id，获取指定的被操作的语雀文档所在的专题库名称
        :param repo: 知识库的唯一标识
        :param doc_id: 文档的id
        :param action: 文档的操作类型 publish, update, delete
        :return:
        """
        # 1、获取当前知识库的所有目录
        if action == "delete":
            toc_list = self.repo2tocs_map[repo]
        else:
            toc_list = self.list_yuque_toc(repo)
            self.repo2tocs_map[repo] = toc_list.copy()
        # 2、构建知识库的目录树并获取当前文档的uuid
        nodes_tree = {}
        root_title_map = {}
        doc_uuid = None
        for toc in toc_list:
            if toc["doc_id"] == doc_id:
                doc_uuid = toc["uuid"]
                print(f"doc_title:{toc['title']}")
            if toc["parent_uuid"] != "":
                nodes_tree[toc["uuid"]] = toc["parent_uuid"]
            else:
                root_title_map[toc["uuid"]] = toc["title"]
        current_uuid = doc_uuid
        if doc_uuid is None:
            return None, None
        while current_uuid in nodes_tree:
            current_uuid = nodes_tree[current_uuid]
        return root_title_map.get(current_uuid, None), current_uuid

    def _get_uuid_by_title(self,repo: str, toc_title: str) -> str:
        """
        根据目录title获取uuid
        :param repo: 知识库的唯一标识
        :param toc_title: 目录title,对应知识库的专题库
        :return: uuid or None
        """
        # 遍历目录，找到目录title对应的uuid
        if repo in self.repo2tocs_map:
            tocs = self.repo2tocs_map[repo]
        else:
            tocs = self.list_yuque_toc(repo)
            self.repo2tocs_map[repo] = tocs
        for toc in tocs:
            if toc["title"] == toc_title and toc["parent_uuid"] == "":
                return toc["uuid"]
        return None

    def _get_tocs_from_parent(self,repo: str, toc_uuid: str, top_uuid: str = None) -> List[dict]:
        """
        根据父级目录的uuid获取子目录
        :param repo: 知识库的唯一标识
        :param toc_uuid: 父级目录的uuid
        :param top_uuid: 最顶级的uuid
        """
        result = []
        if not top_uuid:
            # 如果不传top_uuid,则top_uuid就是当前toc_uuid
            top_uuid = toc_uuid
        # 1、获取当前知识库的所有目录
        if repo in self.repo2tocs_map:
            tocs = self.repo2tocs_map[repo].copy()
        else:
            tocs = self.list_yuque_toc(repo)
            self.repo2tocs_map[repo] = tocs.copy()
        # 2、遍历目录，找到父级目录uuid对应的子目录
        for toc in tocs:
            if toc["parent_uuid"] == toc_uuid:
                # 给语雀返回的对象添加一个额外的repo和top_uuid字段，供后续业务使用
                toc["repo"] = repo
                toc["top_uuid"] = top_uuid
                result.append(toc)
        return result

    def _get_doc_from_tocs(self,tocs: List[dict]) -> List[dict]:
        """
        将目录列表转化为文档列表（展开TITLE的目录）
        :param tocs: 目录列表
        :return: 文档列表
        """
        docs = []
        for toc in tocs:
            if toc["type"] == "TITLE":
                child_tocs = self._get_tocs_from_parent(toc["repo"], toc["uuid"], toc["top_uuid"])
                docs.extend(self._get_doc_from_tocs(child_tocs))
            elif toc["type"] == "DOC":
                child_tocs = self._get_tocs_from_parent(toc["repo"], toc["uuid"], toc["top_uuid"])
                if child_tocs:
                    # 文档类型的节点有子文档，需要忽略该文档
                    docs.extend(self._get_doc_from_tocs(child_tocs))
                else:
                    # 文档类型的节点没有子文档，就是单纯的一个文档
                    doc = self.get_single_doc(toc["repo"], toc["slug"])
                    doc["top_uuid"] = toc["top_uuid"]
                    doc["repo"] = toc["repo"]
                    docs.append(doc)
        return docs

    def list_yuque_toc(self,repo: str) -> List[dict]:
        """
        获取语雀指定知识库的目录
        :param repo: 知识库的唯一标识
        :return: 目录列表
        """
        url = f"{self.YUQUE_BASE_URL}/repos/{self.YUQUE_NAMESPACE}/{repo}/toc"
        headers = {
            "X-Auth-Token": self.YUQUE_AUTH_TOKEN,
            "User-Agent": self.YUQUE_REQUEST_AGENT
        }

        logger.info(f"请求获取语雀目录 {url}")
        try:
            response = requests.get(url=url, headers=headers)
            response.raise_for_status()
            return json.loads(response.text)["data"]
        except requests.exceptions.RequestException as e:
            logger.error(f"请求获取语雀目录 {url} 失败: {str(e)}")
            raise Exception("请求获取语雀目录失败")

    def get_single_doc(self,repo: str, slug: str) -> dict:
        """
        获取单个语雀文档
        :param repo: 知识库的唯一标识
        :param slug: url中的slug
        :return: 文档详情
        """
        url = f"{self.YUQUE_BASE_URL}/repos/{self.YUQUE_NAMESPACE}/{repo}/docs/{slug}"
        headers = {
            "X-Auth-Token": self.YUQUE_AUTH_TOKEN,
            "User-Agent": self.YUQUE_REQUEST_AGENT
        }
        logger.info(f"请求获取单个语雀文档 {url}")
        try:
            response = requests.get(url=url, headers=headers)
            response.raise_for_status()
            return json.loads(response.text)["data"]
        except requests.exceptions.RequestException as e:
            logger.error(f"请求获取单个语雀文档 {url} 失败: {str(e)}")
            raise Exception("请求获取单个语雀文档失败")