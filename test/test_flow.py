import sys
import os
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root_dir)

from config.settings import *
from src.utils.common_utils import get_all_yq_repo
from src.sync.sync_flow import SyncFlow
from src.utils.logger import logger

if __name__ == '__main__':
    yuque_repos = get_all_yq_repo()
    if USE_AZURE_OPENAI:
        logger.info("使用 Azure OpenAI")
        asst_sync_flow = SyncFlow(
            yuque_base_url=YUQUE_BASE_URL, yuque_namespace=YUQUE_NAMESPACE,
            yuque_auth_token=YUQUE_AUTH_TOKEN, yuque_request_agent=YUQUE_REQUEST_AGENT,
            sync_destination_name=ASSISTANT_NAME, file_num_limit=ASSISTANT_FILE_NUM_LIMIT,
            file_token_limit=ASSISTANT_FILE_TOKEN_LIMIT, yuque_repos=yuque_repos,
            api_key=AZURE_OPENAI_API_KEY, azure_endpoint=AZURE_OPENAI_ENDPOINT, api_version=OPENAI_API_VERSION)
        assistant_id = "asst_dI1uzWr3Lpo3iHKHhk8gwT1c"
    else:
        logger.info("使用 OpenAI")
        asst_sync_flow = SyncFlow(
            yuque_base_url=YUQUE_BASE_URL, yuque_namespace=YUQUE_NAMESPACE,
            yuque_auth_token=YUQUE_AUTH_TOKEN, yuque_request_agent=YUQUE_REQUEST_AGENT,
            sync_destination_name=ASSISTANT_NAME, file_num_limit=ASSISTANT_FILE_NUM_LIMIT,
            file_token_limit=ASSISTANT_FILE_TOKEN_LIMIT, yuque_repos=yuque_repos,
            api_key=OPENAI_API_KEY)
        assistant_id = "asst_G5t60WEtbD9ygU5n2Ol727N6"
    # 测试 同步流程
    asst_sync_flow.sync_yq_topicdata_to_asst(repo="dn5ehb", toc_title="乐企", assistant_id=assistant_id)