import os
import pickle
import time

from langchain.embeddings import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores.faiss import FAISS
from langchain.document_loaders import UnstructuredMarkdownLoader
from config import OPENAI_API_KEY, FAISS_DB_PATH

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
def restore_url(path):
    names = path.split('/')
    tile_slug = names[-1].split('%2F')
    title = tile_slug[-2] if len(tile_slug) > 1 else tile_slug[-1]
    slug = tile_slug[-1].replace('.md', '')
    rn = names[-2].split('%2F')
    repo_id = rn[-1]
    namespace = rn[-2]
    return title, "https://www.yuque.com/%s/%s/%s" % (namespace, repo_id, slug)


def prepare_dir_dataset(base_dir, db=None):
    total = 0
    for i in findAllFile(base_dir, file_type='md'):
        loader = UnstructuredMarkdownLoader(i)

        raw_documents = loader.load()
        # 将文档的在线url重构出来
        for doc in raw_documents:
            doc.metadata['title'], doc.metadata['url'] = restore_url(i)

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=300,
            chunk_overlap=50,
        )

        documents = text_splitter.split_documents(raw_documents)

        if db is None:
            # create and load faiss with documents
            db = FAISS.from_documents(documents, embedding=embeddings)
        else:
            db.add_documents(documents)

        total += 1
        print(f"Processed[{total}]: {i}")

    # Save vectorstore
    if db is not None:
        db.save_local(FAISS_DB_PATH)
        print("Saved vectors to %s" % FAISS_DB_PATH)


# 导入语雀导出的md文件到vector db，针对知识库piaozone/implement
def ingest_yq_piaozone_implement():
    path = '/Users/qinqiang02/Desktop/fpy知识库/piaozone%2Fimplement_'
    # 手工切分文件夹，避免一次性处理太多文件，导致openai api超限
    for i in range(11):
        doc_path = path + f"{i + 1}"

        print("Processing path: %s" % doc_path)
        try:
            rds = FAISS.load_local(FAISS_DB_PATH, embeddings)
            print("Using existing db: %s" % FAISS_DB_PATH)
            prepare_dir_dataset(doc_path, rds)
        except Exception as e:
            print("No db found, create one")
            prepare_dir_dataset(doc_path)

        print("Processed path: %s" % doc_path)

        time.sleep(60)


# 导入语雀导出的md文件到vector db，针对数据量不大的知识库
def ingest_yq_other():
    doc_path = '/Users/qinqiang02/workspace/ml/redis-langchain-chatbot/fpy/data_md'

    print("Processing path: %s" % doc_path)
    try:
        rds = FAISS.load_local(FAISS_DB_PATH, embeddings)
        print("Using existing db: %s" % FAISS_DB_PATH)
        prepare_dir_dataset(doc_path, rds)
    except Exception as e:
        print("No db found, create one")
        prepare_dir_dataset(doc_path)

    print("Processed path: %s" % doc_path)


if __name__ == "__main__":
    ingest_yq_piaozone_implement()
