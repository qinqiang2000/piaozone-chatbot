from collections import defaultdict
from itertools import chain
from langchain.vectorstores import FAISS
from langchain.embeddings import OpenAIEmbeddings
import os
from config import OPENAI_API_KEY, INDEX_NAME, REDIS_URL, FAISS_DB_PATH

# set your openAI api key as an environment variable
os.environ['OPENAI_API_KEY'] = OPENAI_API_KEY

def feq_sort(*lists):
    counter = defaultdict(int)
    for x in chain(*lists):
        counter[x] += 1
    return [key for (key, value) in
        sorted(counter.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)]


def get_citations(results):
    links ={}
    urls = []
    for r in results:
        urls.append(r.metadata['url'])
        links[r.metadata['url']] = r.metadata['title']

    citations = [f"[{links[u]}]: {u}" for u in feq_sort(urls)]
    return citations


def db_test(rds):
    query = "如何查看剩余票量？"
    results = rds.similarity_search_with_score(query)
    print(results)
    print(get_citations(results))


if __name__ == "__main__":
    embeddings = OpenAIEmbeddings()
    try:
        rds = FAISS.load_local(
            "../" + FAISS_DB_PATH,
            embeddings
        )
        db_test(rds)
    except Exception as e:
        print("No db found, create one")