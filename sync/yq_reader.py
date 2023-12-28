"""
语雀reader模块，提供读取语雀知识库文档的能力
"""

import json
import requests
from config.settings import *


def get_docs(repo, toc_title):
    """
    获取语雀文档
    :param repo: 库名
    :param toc_title: 目录title
    :return:
    """
    toc_uuid = get_uuid_by_title(repo, toc_title)

    # 获取目录下所有文档
    tocs = get_tocs_from_parent(repo, toc_uuid)
    docs = get_doc_from_tocs(tocs)

    return docs


def get_uuid_by_title(repo, toc_title):
    """
    根据目录title获取uuid
    :param repo:
    :param toc_title:
    :return:
    """
    tocs = list_yuque_toc(repo)
    for toc in tocs:
        if toc["title"] == toc_title:
            return toc["uuid"]
    return None


def get_tocs_from_parent(repo, toc_uuid, top_uuid=None):
    """
    根据父级uuid获取子目录
    :param top_uuid: 最顶级的uuid
    """
    result = []
    if not top_uuid:
        # 如果不传top_uuid则是当前toc_uid
        top_uuid = toc_uuid
    tocs = list_yuque_toc(repo)
    for toc in tocs:
        if toc["parent_uuid"] == toc_uuid:
            # 给语雀返回的对象添加一个额外的repo和top_uuid字段，供后续业务使用
            toc["repo"] = repo
            toc["top_uuid"] = top_uuid
            result.append(toc)
    return result


def get_doc_from_tocs(tocs):
    """
    将目录列表转化为文档列表（展开TITLE的目录）
    """
    docs = []
    for toc in tocs:
        if toc["type"] == "TITLE":
            child_tocs = get_tocs_from_parent(toc["repo"], toc["uuid"], toc["top_uuid"])
            docs.extend(get_doc_from_tocs(child_tocs))
        elif toc["type"] == "DOC":
            child_tocs = get_tocs_from_parent(toc["repo"], toc["uuid"], toc["top_uuid"])
            if child_tocs:
                # 文档类型的节点有子文档，需要忽略该文档
                docs.extend(get_doc_from_tocs(child_tocs))
            else:
                # 文档类型的节点没有子文档，就是单纯的一个文档
                doc = get_yuque_doc(toc["repo"], toc["slug"])
                doc["top_uuid"] = toc["top_uuid"]
                doc["repo"] = toc["repo"]
                docs.append(doc)
    return docs


def list_yuque_toc(repo):
    """
    获取语雀目录
    :param repo:
    :return:
    """
    url = f"{YUQUE_BASE_URL}/repos/{YUQUE_NAMESPACE}/{repo}/toc"
    logging.info(f"请求获取语雀目录{url}")
    response = requests.get(url=url,
                            headers={"X-Auth-Token": YUQUE_AUTH_TOKEN,
                                     "User-Agent": YUQUE_REQUEST_AGENT})
    if response.status_code != 200:
        logging.error(f"请求获取语雀目录{url}失败,返回码为{response.status_code}")
        raise Exception("请求获取语雀目录失败")
    return json.loads(response.text)["data"]


def get_yuque_doc(repo, slug):
    """
    获取单个语雀文档
    :param repo:
    :param slug:
    :return:
    """
    url = f"{YUQUE_BASE_URL}/repos/{YUQUE_NAMESPACE}/{repo}/docs/{slug}"
    logging.info(f"请求获取单个语雀文档{url}")
    response = requests.get(url=url, headers={"X-Auth-Token": YUQUE_AUTH_TOKEN,
                                              "User-Agent": YUQUE_REQUEST_AGENT})
    if response.status_code != 200:
        logging.error(f"请求获取单个语雀文档{url}失败,返回码为{response.status_code}")
        raise Exception("请求获取单个语雀文档失败")
    return json.loads(response.text)["data"]