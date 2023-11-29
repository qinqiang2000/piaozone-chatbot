import requests

from assistant import Assistant
from settings import *
from common_utils import *


def update_yuque_doc(repo, doc, new_content):
    url = f"{YUQUE_BASE_URL}/repos/{YUQUE_NAMESPACE}/{repo}/docs/{doc['id']}"
    response = requests.put(url, headers={"X-Auth-Token": YUQUE_AUTH_TOKEN,
                                          "User-Agent": YUQUE_REQUEST_AGENT}, data={"body": new_content,
                                                                                    "title": doc["title"],
                                                                                    "slug": doc["slug"]})
    if response.status_code != 200:
        logging.error(f"请求修改单个语雀文档{url}失败,返回码为{response.status_code}")
        raise Exception("请求修改单个语雀文档失败")


def get_yuque_doc(repo, slug):
    """
    获取单个语雀文档
    :param repo:
    :param slug:
    :return:
    """
    url = f"{YUQUE_BASE_URL}/repos/{YUQUE_NAMESPACE}/{repo}/docs/{slug}"
    response = requests.get(url=url, headers={"X-Auth-Token": YUQUE_AUTH_TOKEN,
                                              "User-Agent": YUQUE_REQUEST_AGENT})
    if response.status_code != 200:
        logging.error(f"请求获取单个语雀文档{url}失败,返回码为{response.status_code}")
        raise Exception("请求获取单个语雀文档失败")
    return json.loads(response.text)["data"]


def list_yuque_toc(repo):
    """
    获取语雀目录
    :param repo:
    :return:
    """
    url = f"{YUQUE_BASE_URL}/repos/{YUQUE_NAMESPACE}/{repo}/toc"
    response = requests.get(url=url,
                            headers={"X-Auth-Token": YUQUE_AUTH_TOKEN,
                                     "User-Agent": YUQUE_REQUEST_AGENT})
    if response.status_code != 200:
        logging.error(f"请求获取语雀目录{url}失败,返回码为{response.status_code}")
        raise Exception("请求获取语雀目录失败")
    return json.loads(response.text)["data"]


def get_tocs_from_parent(repo, toc_uuid, top_uuid=None):
    """
    根据父级uuid获取子目录
    :param top_uuid: 最顶级的uuid
    :param repo:
    :param toc_uuid:
    :return:
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
    :param tocs:
    :return:
    """
    docs = []
    for toc in tocs:
        if toc["type"] == "TITLE":
            child_tocs = get_tocs_from_parent(toc["repo"], toc["uuid"], toc["top_uuid"])
            docs.extend(get_doc_from_tocs(child_tocs))
        elif toc["type"] == "DOC":
            doc = get_yuque_doc(toc["repo"], toc["slug"])
            doc["top_uuid"] = toc["top_uuid"]
            doc["repo"] = toc["repo"]
            docs.append(doc)
    return docs


def upload_docs_2_assistant(docs, assistant_id):
    """
    将语雀的lake文件并拥有body_html内容的文件平均上传到assistant，并将返回的文件id存储下来
    :param assistant_id:
    :param docs:
    :return:
    """
    html_docs = []
    faq_docs = []
    for doc in docs:
        if doc["format"] == "lake" and doc["body_html"]:
            html_docs.append(doc)
        elif doc["format"] == "markdown" and "faq" in doc["title"].lower() and doc["body"]:
            # 名称带有faq的markdown文档
            faq_docs.append(doc)
    assistant = Assistant(assistant_id)
    operate_faq_doc(assistant, faq_docs)
    operate_common_docs(assistant, html_docs)


def operate_faq_doc(assistant, faq_docs):
    """
    处理FAQ.md文档，并上传到assistant
    :param assistant:
    :param faq_docs: 正常应该只有一个
    :return:
    """
    last_faq_file_id = get_config(assistant.assistant_id, "last_faq_file_id")
    if last_faq_file_id:
        assistant.del_file(last_faq_file_id)
    faq_bodies = ""
    yuque_relate_and_faq_slug = {}
    for faq_doc in faq_docs:
        key = faq_doc["repo"] + "/" + faq_doc["top_uuid"]
        if not yuque_relate_and_faq_slug.get(key):
            yuque_relate_and_faq_slug[key] = []
        faq_bodies += faq_doc["body"] + "\n"
        yuque_relate_and_faq_slug[key].append(faq_doc["slug"])
    with open("faq.md", "w", encoding="utf-8") as file:
        file.write(faq_bodies)
    # 上传faq文件
    assistant_file = assistant.create_file("faq.md")
    # 删除临时faq文件
    os.remove("faq.md")
    # 存储本次语雀关联数据
    save_config(assistant.assistant_id, "yuque_relate_and_faq_slug", yuque_relate_and_faq_slug)
    # 存储本次faq文件id
    save_config(assistant.assistant_id, "last_faq_file_id", assistant_file.id)


def operate_common_docs(assistant, html_docs):
    """
    处理除了FAQ.md文档外的普通文档，并上传到assistant
    :param assistant:
    :param html_docs:
    :return:
    """
    operated_files = distribute_common_files(html_docs)
    last_common_file_ids = get_config(assistant.assistant_id, "last_common_file_ids")
    # 删除旧文件
    for common_file_id in last_common_file_ids:
        assistant.del_file(common_file_id)
    common_file_ids = []
    # 新增文件
    for operated_file in operated_files:
        assistant_file = assistant.create_file(operated_file.name)
        common_file_ids.append(assistant_file.id)
        # 删除临时文件
        os.remove(operated_file.name)
    # 存储本次文件id
    save_config(assistant.assistant_id, "last_common_file_ids", common_file_ids)


def distribute_common_files(docs):
    """
    将文件内容平均分配到ASSISTANT_FILE_NUM个文件位中
    :param docs:
    :return:
    """
    # 对输入文件数组按word_count进行排序（从大到小）
    sorted_docs = sorted(docs, key=lambda x: x["word_count"], reverse=True)

    word_count_buckets = [[] for _ in range(ASSISTANT_FILE_NUM)]
    doc_buckets = [[] for _ in range(ASSISTANT_FILE_NUM)]
    file_buckets = []
    # 初始化ASSISTANT_FILE_NUM个文件
    for index in range(ASSISTANT_FILE_NUM):
        with open(str(index + 1) + ".html.tmp", 'w', encoding="utf-8") as file:
            file.write("")
            file_buckets.append(file)

    single_doc_end_format = f"<br><b>{SINGLE_DOC_END}</b><br>"
    # 对于排序后的每个元素，找到当前总和最小的桶，并将其放入
    for doc in sorted_docs:
        # 计算每个文件的字数总和
        word_count_bucket_sums = [sum(count_bucket) for count_bucket in word_count_buckets]

        # 找到总和最小的文件的索引
        min_bucket_index = word_count_bucket_sums.index(min(word_count_bucket_sums))

        word_count_buckets[min_bucket_index].append(doc["word_count"])
        doc_buckets[min_bucket_index].append(doc)
        # 在对应文件位的文件开头和末尾添加当前文件内容
        with open(file_buckets[min_bucket_index].name, "a", encoding="utf-8") as file:
            file.write(doc["body_html"])
            file.write(single_doc_end_format.format(doc["title"], doc["word_count"]))

    add_index_in_doc_start(file_buckets, doc_buckets)
    return file_buckets


def add_index_in_doc_start(file_buckets, doc_buckets):
    """
    给每个文件的开头添加索引
    :param file_buckets:
    :param doc_buckets:
    :return:
    """
    chunk_size = 1024 * 1024
    for index in range(ASSISTANT_FILE_NUM):
        with open(file_buckets[index].name, "r", encoding="utf-8") as ori_file, \
                open(ori_file.name[:-len(".tmp")], "w", encoding="utf-8") as file:
            file.write("<b>文件索引：</b><br>")
            word_count_sum = 0
            for doc in doc_buckets[index]:
                file.write(f"《{doc['title']} 》开始位置（字数）：{word_count_sum} <br>")
                etra_word_count = len(SINGLE_DOC_END.format(doc["title"], doc["word_count"]))
                word_count_sum += doc["word_count"] + etra_word_count
            file.write("<b>===================================索引分割============================================</b>")
            # 分块复制文件
            while True:
                chunk = ori_file.read(chunk_size)
                if not chunk:
                    break
                file.write(chunk)
            file_buckets[index] = file
        # 删除旧.tmp结尾文件
        os.remove(file_buckets[index].name + ".tmp")


def sync_yuque_docs_2_assistant(repo=None, toc_uuid=None, assistant_id=None):
    """
    同步语雀文档到assistant，三个参数都传则表示手动指定同步
    :param repo:
    :param toc_uuid:
    :param assistant_id:
    :return:
    """
    # 手动同步
    if repo and toc_uuid and assistant_id:
        logging.info(f"同步库{repo}目录id为{toc_uuid}的所有文件到assistant {assistant_id}")
        upload_docs_2_assistant(get_doc_from_tocs(get_tocs_from_parent(repo, toc_uuid)), assistant_id)
        return
    # 定时任务同步
    config = get_config()
    for assistant_id in list(config.keys()):
        tocs = []
        for repo_and_toc_uuid in config[assistant_id]["yuque_relate_and_faq_slug"]:
            arr = repo_and_toc_uuid.split("/")
            repo = arr[0]
            toc_uuid = arr[1]
            logging.info(f"同步库{repo}目录id为{toc_uuid}的所有文件到assistant {assistant_id}")
            tocs.extend(get_tocs_from_parent(repo, toc_uuid))
        upload_docs_2_assistant(get_doc_from_tocs(tocs), assistant_id)
