import os
from enum import Enum
from dotenv import load_dotenv

from src.qa_assistant.base_assistant import ASSTType
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(override=True)

################## assistant配置 ##################
# 1.直接使用openai assistant自带的retrieval工具实现的问答助手
ASSISTANT_CONFIG = {
    ASSTType.NATIVE_ASST:{
        "asst_type": ASSTType.NATIVE_ASST,
        # 详见 src/qa_assistant/base_assistant.py的 ASSTType, options: 0, 1; 0: NATIVE_ASST, 1: ASST_WITH_SIMPLE_RAG
        "llm_option": "openai",  # 详见 src/qa_assistant/base_assistant.py的 ASSTLLMType, options: "openai", "azure"
        "llm_config": {
            "openai": {
                "openai_api_key": os.getenv("OPENAI_API_KEY"),
                "model_name": "gpt-4o"
            },
            "azure": {
                "azure_openai_api_key": os.getenv("AZURE_OPENAI_API_KEY"),
                "openai_api_version": os.getenv("OPENAI_API_VERSION"),
                "azure_openai_endpoint": os.getenv("AZURE_OPENAI_ENDPOINT"),
                "model_name": os.getenv("OPENAI_DEPLOYMENT_NAME")
            }
        },
        # "chunking_strategy":{},
        "sync_flow_config": {
            "id":"sync_dest_0", #用于识别不同的同步流程
            "type":"openai-asst",
            "params":{
                "file_num_limit": 10000,
                "file_token_limit": 5000000
            }

        }
    }
} #每一个assistant 的asst_type不能重复
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
CONFIG_REPO = "kro38t" #配置文件所在语雀知识库id
CONFIG_SLUG = "en71melffu178kvp" #配置文件的文档slug

################## 云之家配置 ##################
YUNZHIJIA_CONFIG = {
    "notify_url": "https://www.yunzhijia.com/gateway/robot/webhook/send?yzjtype=0&yzjtoken={}",
    "max_img_num_in_card_notice": 5,
    "card_notice_template_id": "64d08cb4e4b07ba2b112b395"
}

################## 日志 ##################
LOG_DIR = os.path.join(root_dir, 'logs')
LOG_LEVEL = "debug"

################## celery配置 ##################
CELERY_CONFIG = {
    "broker_url": 'redis://127.0.0.1:6379/0',
    "backend_url": "redis://127.0.0.1:6379/1"}

# PIAOZONE_TOKEN_URL = "https://api-dev.piaozone.com/test/base/exception/login/token"
# PIAOZONE_TOKEN_BODY = "U5/yFNQySPUsjrHqSDUFl58fJ7OxHT8W4KWJqK4tLd/ze1/IIFtmActgeM8VxT4uAUn4cW75sKLbaLXPOMFYTVQ+XJDmwosnJ+qsangGMujLo2S3zQqQ/AU8TUd7qgrdYdEKKBLoTIXeCoBA3jjH4u9h+PvFcwfQuSgJbmKwomc="
# PIAOZONE_ADD_SOBOT_DOC_URL = "https://api-dev.piaozone.com/test/portal/m19/customer-service/sobot-doc/with-yuque-slug?access_token="


