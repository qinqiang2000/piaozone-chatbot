import os
from enum import Enum
from dotenv import load_dotenv

from src.qa_assistant.base_assistant import ASSTType
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(override=True)
################## 大模型平台的相关配置 ##################
LLM_CONFIGS = {
    "azure_openai": {
        "api_key": os.getenv("AZURE_OPENAI_API_KEY"),
        "api_version": os.getenv("OPENAI_API_VERSION"),
        "endpoint": os.getenv("AZURE_OPENAI_ENDPOINT"),
        "model_map_table": {
            "gpt-4o-assistant": "gpt-4o"
        }
    },
    "openai": {
        "api_key": os.getenv("OPENAI_API_KEY"),
    }
}

################## assistant配置 ##################
# 1.NATIVE_ASST: 直接使用openai assistant自带的retrieval工具实现的问答助手
ASSISTANT_CONFIG = {
    "openai_assistant": {
        "asst_type": "openai_assistant",
        # 详见 src/qa_assistant/base_assistant.py的 ASSTType, options: 0, 1; 0: NATIVE_ASST, 1: ASST_WITH_SIMPLE_RAG
        # "llm_option": "openai",  # 详见 LLM_CONFIGS, options: "openai", "azure_openai"
        "sync_flow_config": {
            "id": "sync_dest_0", # 用于识别不同的同步流程
            "type": "openai-asst",
            "params": {
                "file_num_limit": 10000,
                "file_token_limit": 5000000
            }

        }
    }
}
################## 同步设置 ##################
##同步的目的地类型 ： "openai-asst"
SYNC_CONFIGS = []
for asst in ASSISTANT_CONFIG.values():
    SYNC_CONFIGS.append(asst["sync_flow_config"])
################## 语雀配置 ##################
YUQUE_CONFIG = {
    "yuque_auth_token": os.getenv("YUQUE_AUTH_TOKEN"),
    "yuque_namespace": os.getenv("YUQUE_NAMESPACE"),
    "yuque_base_url": os.getenv("YUQUE_BASE_URL"),
    "yuque_request_agent": os.getenv("YUQUE_REQUEST_AGENT"),
    "yuque_access_base_url": os.getenv("YUQUE_ACCESS_BASE_URL") # 语雀文档访问地址
}

################## 配置文件设置 ##################
#语雀知识库、ai助手、云之家群关系的配置地址
# CONFIG_REPO = "kro38t" #配置文件所在语雀知识库id
# CONFIG_SLUG = "en71melffu178kvp" #配置文件的文档slug
CONFIG_INFO = {
    "asst_info_repo": "kro38t",
    "asst_info_slug": "adg5ul0a6ehvpwpw",
    "yzj_info_repo": "kro38t",
    "yzj_info_slug": "uv7ykd2p34i8vdko",
    "zhichi_info_repo": "kro38t",
    "zhichi_info_slug": "ci28alu28xbv4feb",
 }

################## 云之家配置 ##################
YUNZHIJIA_CONFIG = {
    "notify_url": "https://www.yunzhijia.com/gateway/robot/webhook/send?yzjtype=0&yzjtoken={}",
    "max_img_num_in_card_notice": 5,
    "card_notice_template_id": "64d08cb4e4b07ba2b112b395"
}
################## 自动录入地址配置 ##################
AUTO_ENTRY_CONFIG = {
    "url": f"{YUQUE_CONFIG['yuque_base_url']}/repos/{YUQUE_CONFIG['yuque_namespace']}/kro38t/docs/wthbafwdgo5zw783",
    "headers": {
        "X-Auth-Token": YUQUE_CONFIG["yuque_auth_token"],
        "User-Agent": YUQUE_CONFIG["yuque_request_agent"]
    }
}

################## 日志 ##################
LOG_DIR = os.path.join(root_dir, 'logs')
LOG_LEVEL = "debug"

################# database ################
DB_CONFIG = {
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
    "db": os.getenv("DB_DB"),
    "charset": os.getenv("DB_CHARSET")
}


