import os
from dotenv import load_dotenv
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(override=True)
# 1. 读取环境变量
## openai
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
## azure openai
AZURE_OPENAI_API_KEY = os.getenv('AZURE_OPENAI_API_KEY')
OPENAI_API_VERSION = os.getenv('OPENAI_API_VERSION')
AZURE_OPENAI_ENDPOINT = os.getenv('AZURE_OPENAI_ENDPOINT')
OPENAI_DEPLOYMENT_NAME = os.getenv('OPENAI_DEPLOYMENT_NAME')
USE_AZURE_OPENAI = False
#2. 读取配置文件

## 语雀知识库、ai助手、云之家群关系的配置地址
# CONFIG_PATH = "config/config.yml"
CONFIG_REPO = "kro38t" #配置文件所在知识库id
CONFIG_SLUG = "en71melffu178kvp" #配置文件的文档slug
## 云之家通知地址
YUNZHIJIA_NOTIFY_URL = "https://www.yunzhijia.com/gateway/robot/webhook/send?yzjtype=0&yzjtoken={}"
## 云之家每张卡片消息最大图片数
MAX_IMG_NUM_IN_CARD_NOTICE = 5
## 云之家卡片消息模板id
CARD_NOTICE_TEMPLATE_ID = "64d08cb4e4b07ba2b112b395"

## 语雀配置
YUQUE_AUTH_TOKEN = os.getenv('YUQUE_AUTH_TOKEN')
YUQUE_NAMESPACE = os.getenv('YUQUE_NAMESPACE')  # 语雀团队/空间路径
YUQUE_BASE_URL = os.getenv('YUQUE_BASE_URL')
YUQUE_REQUEST_AGENT = os.getenv('YUQUE_REQUEST_AGENT')

PIAOZONE_TOKEN_URL = "https://api-dev.piaozone.com/test/base/exception/login/token"
PIAOZONE_TOKEN_BODY = "U5/yFNQySPUsjrHqSDUFl58fJ7OxHT8W4KWJqK4tLd/ze1/IIFtmActgeM8VxT4uAUn4cW75sKLbaLXPOMFYTVQ+XJDmwosnJ+qsangGMujLo2S3zQqQ/AU8TUd7qgrdYdEKKBLoTIXeCoBA3jjH4u9h+PvFcwfQuSgJbmKwomc="
PIAOZONE_ADD_SOBOT_DOC_URL = "https://api-dev.piaozone.com/test/portal/m19/customer-service/sobot-doc/with-yuque-slug?access_token="

## 问答助手配置
# 同步的目的地类型 ： "openai-asst", "azure-asst"
SYNC_DEST_TYPE = ["openai-asst"]
# assistant 文件限制
ASSISTANT_FILE_NUM_LIMIT = 20
ASSISTANT_FILE_TOKEN_LIMIT = 2000000
# 3. 日志配置
LOG_DIR = os.path.join(root_dir, 'logs')

