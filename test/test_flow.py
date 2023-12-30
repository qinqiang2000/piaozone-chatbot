import logging

import sync.sync_flow as flow

# 强制设置logging
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S", force=True)

if __name__ == '__main__':
    flow.sync_gpt_from_yq("8843a091baa84f2cb6ab49729ff1221c")
    # flow.sync_gpt_from_cache("8843a091baa84f2cb6ab49729ff1221c")