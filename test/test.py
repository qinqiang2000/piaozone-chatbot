
from itertools import chain
from collections import defaultdict


def feq_sort(*lists):
    counter = defaultdict(int)
    for x in chain(*lists):
        counter[x] += 1
    return [key for (key, value) in
        sorted(counter.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)]


l = ["a", "b",  "b",  "b",  "b", "a", "a", "c"]
print(feq_sort(l))