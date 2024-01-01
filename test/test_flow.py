import logging

import sync.sync_flow as flow

# 强制设置logging
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S", force=True)

if __name__ == '__main__':
    flow.sync_gpt_from_yq("d29fe265a9594811881e86b7e3d8a1e7")
    # flow.sync_gpt_from_cache("8843a091baa84f2cb6ab49729ff1221c")