import logging

from sync.sync_flow import sync_gpt_by_yzj_flow

# 强制设置logging
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S", force=True)

if __name__ == '__main__':
    sync_gpt_by_yzj_flow("d29fe265a9594811881e86b7e3d8a1e7")