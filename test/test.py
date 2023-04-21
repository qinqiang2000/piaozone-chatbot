
from itertools import chain
from collections import defaultdict

from ingest_md import findAllFile


def split_docs():
    import shutil

    path = '/Users/qinqiang02/Desktop/fpy知识库/piaozone%2Fimplement'
    count = 0
    for i in findAllFile(path, file_type='md'):
        count += 1
        dest = path + f"_{int(count / 10) + 1}"
        shutil.move(i, dest)
        print(f"move from {i} to {dest}")

split_docs()

def feq_sort(*lists):
    counter = defaultdict(int)
    for x in chain(*lists):
        counter[x] += 1
    return [key for (key, value) in
        sorted(counter.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)]


l = ["a", "b",  "b",  "b",  "b", "a", "a", "c"]
print(feq_sort(l))