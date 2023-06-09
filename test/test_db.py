from collections import defaultdict
from itertools import chain
from langchain.vectorstores import FAISS
from langchain.embeddings import OpenAIEmbeddings
import os
from settings import OPENAI_API_KEY, INDEX_NAME, REDIS_URL, FAISS_DB_PATH

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
    query = "影像退扫怎么操作？"
    results = rds.similarity_search_with_score(query)
    print([r[0].metadata['title'] for r in results])
    print(results)


if __name__ == "__main__":
    embeddings = OpenAIEmbeddings()
    try:
        rds = FAISS.load_local(
            "../" + FAISS_DB_PATH,
            embeddings
        )
        db_test(rds)
    except Exception as e:
        print(e)
        print("No db found")