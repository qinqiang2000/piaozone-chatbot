
import os
import time
import pandas as pd
from langchain.document_loaders import DataFrameLoader, CSVLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores.faiss import FAISS
from query_data import get_embeddings

embeddings = None
FAISS_DB_PATH = "../db"
doc_dict = {'FAQ_EAS': 'hmuqqwsfsar5y9on', 'FAQ_EAS_实施&二开指导': 'sp8868cpqk7d2h7z', 'FAQ_EAS_常见问题': 'iz9qpvklh74hp4wa'
    , 'FAQ_EAS_操作手册': 'wchtrp7ni3xm9dq5', 'FAQ_EAS_新特性': 'sibbiigwucfw74xy', 'FAQ_EAS_标准操作手册': 'rt4501y72sffd37n'
    , 'FAQ_EAS_知识合辑': 'pmy2i9nskgtabrma', 'FAQ_EAS_补丁介绍': 'lohi9zh89uhpgqg5', 'FAQ_K3WISE': 'si1shf8egopi00pc'
    , 'FAQ_全电': 'gmlckqs9xyp3c3z2', 'FAQ_我家云': 'nfhcyt3lzmcnle3e', 'FAQ_托管': 'to5x5mywmp1ssddd'
    , 'FAQ_星瀚': 'atygimyf2hzpduxz', 'FAQ_星空': 'hezasgdsmwr8b2hk', 'FAQ_星空_通用': 'ml3apn0knwbmfgs0'
    , 'FAQ_运营': 'vvvh1g64yebfvubg', 'FAQ_通用': 'wiovn644rmnf02zu', '文档链接_实施文档': 'ntwn0gedmqk69pma'
    , 'FAQ_商户运营平台': 'yp28tesu0xnd1xdu', '常见问题列表（汇总）20230428': 'me42ixwwhn4u5gta'}


# 遍历文件夹下所有指定类型文件
def findAllFile(base, file_type=None):
    for root, ds, fs in os.walk(base):
        for f in fs:
            if file_type is None or f.endswith('.' + file_type):
                fullname = os.path.join(root, f)
                yield fullname


# 重构出语雀的title和url, 未做异常处理
def restore_yq_url(path):
    names = path.split('/')
    file_ext = names[-1]
    title = file_ext.split('.')[0]
    slug = doc_dict[title]
    return title, f'https://www.yuque.com/piaozone/yipfsg/{slug}?singleDoc'


def prepare_dir_dataset(base_dir, restore_fn, db=None):
    total = 0
    for i in findAllFile(base_dir, file_type='csv'):

        loader = CSVLoader(file_path=i)
        documents = loader.load()

        # 将文档的在线url重构出来
        for doc in documents:
            doc.metadata['title'], doc.metadata['url'] = restore_fn(i)
        print('\n', documents[0])

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


def ingest(doc_path):
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
    embeddings = get_embeddings(api_type='azure')
    path = '/Users/qinqiang02/Desktop/fpy知识库/训练知识'
    ingest(path)
