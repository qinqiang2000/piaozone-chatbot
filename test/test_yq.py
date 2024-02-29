import sys
import os
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root_dir)

import json
import requests


from config.settings import *
from src.sync.yuque_reader import YQReader
from src.utils.common_utils import get_all_yq_repo

if __name__ == '__main__':
    yuque_repos = get_all_yq_repo()
    yqreader = YQReader(yuque_base_url=YUQUE_BASE_URL,
                        yuque_namespace=YUQUE_NAMESPACE,
                        yuque_auth_token=YUQUE_AUTH_TOKEN,
                        yuque_request_agent=YUQUE_REQUEST_AGENT,
                        yuque_repos=yuque_repos)
    # 测试 yq获取目录

    print(yqreader.list_yuque_toc("dn5ehb"))

    # 测试获取单文档
    print(yqreader.get_single_doc("dn5ehb", "nhpf1g6k8m9h9wop"))