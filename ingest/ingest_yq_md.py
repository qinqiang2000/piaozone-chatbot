"""
将语雀导出的Markdown注入向量数据库；
适配另一个工程：ExportMD-rectify-pics导出的Markdown；
ExportMD-rectify-pics工程通过一定规则命名Markdown文件名及上级目录名，方便本代码还原出该Markdown其对应的语雀的url
"""

import os
import time

from langchain.embeddings import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter, MarkdownTextSplitter
from langchain.vectorstores.faiss import FAISS
from langchain.document_loaders import UnstructuredMarkdownLoader

from settings import OPENAI_API_KEY

FAISS_DB_PATH = "../db"

# set your openAI api key as an environment variable
os.environ['OPENAI_API_KEY'] = OPENAI_API_KEY

embeddings = OpenAIEmbeddings()

# 遍历文件夹下所有指定类型文件
def findAllFile(base, file_type=None):
    for root, ds, fs in os.walk(base):
        for f in fs:
            if file_type is None or f.endswith('.' + file_type):
                fullname = os.path.join(root, f)
                yield fullname


# 重构出语雀的title和url
def restore_yq_url(path):
    names = path.split('/')
    tile_slug = names[-1].split('%2F')
    title = tile_slug[-2] if len(tile_slug) > 1 else tile_slug[-1]
    slug = tile_slug[-1].replace('.md', '')
    rn = names[-2].split('%2F')
    repo_id = rn[-1]
    namespace = rn[-2]
    return title, "https://www.yuque.com/%s/%s/%s" % (namespace, repo_id, slug)


def prepare_dir_dataset(base_dir, restore_fn, db=None):
    total = 0
    for i in findAllFile(base_dir, file_type='md'):
        loader = UnstructuredMarkdownLoader(i)

        raw_documents = loader.load()
        # 将文档的在线url重构出来
        for doc in raw_documents:
            doc.metadata['title'], doc.metadata['url'] = restore_fn(i)

        text_splitter = MarkdownTextSplitter(
            chunk_size=1000,
            chunk_overlap=100,
        )

        documents = text_splitter.split_documents(raw_documents)

        if db is None:
            # create and load faiss with documents
            db = FAISS.from_documents(documents, embedding=embeddings)
        else:
            db.add_documents(documents)

        total += 1
        print(f"Processed[{total}]: {i}")

        # 每10个文档休眠一次， 避免被openai限流
        if total / 10 == 0:
            time.sleep(15)

    # Save vectorstore
    if db is not None:
        db.save_local(FAISS_DB_PATH)
        print("Saved vectors to %s" % FAISS_DB_PATH)


# 将语雀导出的md文件注入vector db，针对数据量不大的知识库
def ingest_yq_md(doc_path):
    print("Processing path: %s" % doc_path)
    try:
        rds = FAISS.load_local(FAISS_DB_PATH, embeddings)
        print("Using existing db: %s" % FAISS_DB_PATH)
        prepare_dir_dataset(doc_path, restore_yq_url, rds)
    except Exception as e:
        print("No db found, create one")
        prepare_dir_dataset(doc_path, restore_yq_url)

    print("Processed path: %s" % doc_path)


if __name__ == "__main__":
    path = '/Users/qinqiang02/workspace/python/ExportMD-rectify-pics/yuque'
    ingest_yq_md(path)
