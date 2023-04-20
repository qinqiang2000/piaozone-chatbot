import os
import pickle
from langchain.embeddings import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores.faiss import FAISS
from langchain.document_loaders import UnstructuredMarkdownLoader
from config import OPENAI_API_KEY, FAISS_DB_PATH

# set your openAI api key as an environment variable
os.environ['OPENAI_API_KEY'] = OPENAI_API_KEY


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


def prepare_dir_dataset(base_dir):
    docs = []
    for i in findAllFile(base_dir, file_type='md'):
        loader = UnstructuredMarkdownLoader(i)

        raw_documents = loader.load()
        # 将文档的在线url重构出来
        for doc in raw_documents:
            doc.metadata['title'], doc.metadata['url'] = restore_url(i)

        docs = docs + raw_documents

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=300,
        chunk_overlap=50,
    )

    documents = text_splitter.split_documents(docs)

    # create and load redis with documents
    db = FAISS.from_documents(
        documents,
        embedding=OpenAIEmbeddings(),
        # index_name=INDEX_NAME,
        # redis_url=REDIS_URL
    )

    # Save vectorstore
    db.save_local(FAISS_DB_PATH)

def db_test():
    query = "如何配置发票红冲的预警？"
    # results = rds.similarity_search(query)
    # print(results[0].page_content)


if __name__ == "__main__":
    prepare_dir_dataset('/Users/qinqiang02/workspace/ml/redis-langchain-chatbot/fpy/data_md')