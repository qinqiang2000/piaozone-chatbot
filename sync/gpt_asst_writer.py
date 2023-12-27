import re

from openai import OpenAI

from config.settings import *

client = OpenAI()
tmp_dir = os.path.join(os.path.dirname(__file__), "../tmp")


# 同步docs到gpt assistant的文件
def sync_data(docs, id=None):
    if not docs or not id:
        logging.error(f"同步数据到gpt assistant失败，参数有误: {id}")
        return False

    try:
        # 拆分文档为faq和普通文档(取语雀body_html格式内容)
        html_docs, faq_docs = split_docs(docs)

        # 处理faq
        faq_path = transform_faq(faq_docs, id)

        # 处理普通文档
        html_path = transform_docs(html_docs, id)

        # 清空原有数据
        if empty_files(id) < 0:
            logging.error(f"同步数据gpt assistant失败，无法清空原有数据：{id}")
            return False

        # 上传faq文件
        create_file(faq_path, id)

        # 上传普通文件
        for f in html_path:
            create_file(f, id)
    except Exception as e:
        logging.error(f"同步数据到gpt assistant失败：{e}")
        return False

    return True


def split_docs(docs):
    """
    拆分文档为faq和普通文档(取语雀body_html格式内容)
    """
    html_docs = []
    faq_docs = []
    for doc in docs:
        if (doc["format"] == "markdown" or doc["format"] == "lake") \
                and "faq" in doc["title"].lower() and doc["body"]:
            faq_docs.append(doc)
        elif doc["format"] == "lake" and doc["body"]:
            html_docs.append(doc)
    return html_docs, faq_docs


def transform_faq(faq_docs, assistant_id):
    if not faq_docs:
        logging.warning("语雀文档中没有符合faq规定的相关文档，请检查")
        return

    faq_bodies = "\n".join([faq_doc["body"] for faq_doc in faq_docs])

    faq_path = os.path.join(tmp_dir, f"{assistant_id}/faq.md")
    if not os.path.exists(os.path.dirname(faq_path)):
        os.makedirs(os.path.dirname(faq_path))

    with open(faq_path, "w", encoding="utf-8") as file:
        file.write(faq_bodies)

    return faq_path


def transform_docs(html_docs, assistant_id):
    if len(html_docs) == 0:
        logging.warning("语雀文档中没有复合规定的相关文档，请检查")
        return

    base_path = os.path.join(tmp_dir, f"{assistant_id}")
    if not os.path.exists(os.path.dirname(base_path)):
        os.makedirs(os.path.dirname(base_path))

    # 将文档内容分配到多个文件中，以应对gpt assistant的文件上限
    operated_files = distribute_docs(html_docs, base_path)

    file_path = [os.path.join(base_path, f.name) for f in operated_files]

    return file_path


def create_file(file_path, assistant_id):
    # 上传新文件
    with open(file_path, "rb") as f:
        file = client.files.create(
            file=f,
            purpose='assistants'
        )
        # 加载到新文件到assistant
        assistant_file = client.beta.assistants.files.create(
            assistant_id=assistant_id,
            file_id=file.id
        )
        logging.info(f"已上传文件：{file_path}，文件id：{assistant_file.id}")
        return assistant_file


def empty_files(assistant_id):
    """
    :param 清空assistant的文件
    :return: 清空的文件数量；-1 表示清空失败
    """
    try:
        assistant_files = client.beta.assistants.files.list(
            assistant_id=assistant_id,
            limit=100
        )

        deleted_id = []
        for file in assistant_files.data:
            client.beta.assistants.files.delete(assistant_id=assistant_id, file_id=file.id)
            client.files.delete(file.id)
            deleted_id.append(file.id)

        logging.info(f"已清空assistant文件：{deleted_id}，共{len(deleted_id)}个")
        return len(deleted_id)
    except Exception as e:
        logging.error(f"清空assistant文件失败：{e}")
        return -1


def distribute_docs(docs, base_path="./tmp"):
    """
    将文件内容平均分配到ASSISTANT_FILE_NUM_LIMIT个文件中
    :param docs:
    :param base_path: 保存结果的路径
    :return:
    """
    act_num_more_less = False
    limit = ASSISTANT_FILE_NUM_LIMIT
    if len(docs) < limit:
        # 语雀文档实际数量小于assistant的文件上限数，则无需分配，直接按顺序存储即可
        logging.info("语雀实际文档数小于assistant的文件上限数，一个语雀文档对应一个assistant文件即可")
        limit = len(docs)
        act_num_more_less = True

    file_buckets = []
    if act_num_more_less:
        for index in range(limit):
            # 语雀实际文档数小于assistant的文件上限数，一个语雀文档对应一个assistant文件即可
            doc = docs[index]
            file_path = os.path.join(base_path, str(index + 1) + ".md")
            with open(file_path, "w", encoding="utf-8") as file:
                body = transform_md_body(doc["body"], doc["title"])
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
                body = transform_md_body(doc["body"], doc["title"])
                file.write(body)
        add_index_in_doc_start(file_buckets, doc_buckets, base_path)

    return file_buckets


def add_index_in_doc_start(file_buckets, doc_buckets, base_path="./tmp"):
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


def transform_md_body(body, title):
    body = re.sub("<a name=\".*\"></a>", "", body)  # 正则去除语雀导出的<a>标签
    body = re.sub("\x00", "", body)  # 去除不可见字符\x00
    body = re.sub("\x05", "", body)  # 去除不可见字符\x05
    body = re.sub(r'\<br \/\>!\[image.png\]', "\n![image.png]", body)  # 正则去除语雀导出的图片后紧跟的<br \>标签
    body = re.sub(r'\)\<br \/\>', ")\n", body)  # 正则去除语雀导出的图片后紧跟的<br \>标签
    body = f"# {title} \n" + body
    return body