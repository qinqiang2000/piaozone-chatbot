import logging
import os
from dotenv import load_dotenv

logging.basicConfig(format='[%(asctime)s %(filename)s:%(lineno)d] %(levelname)s: %(message)s', level=logging.DEBUG)

load_dotenv(override=True)

# openai
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# azure openai
AZURE_API_KEY = os.getenv('AZURE_API_KEY')
AZURE_BASE_URL = os.getenv('AZURE_BASE_URL')
AZURE_DEPLOYMENT_NAME = os.getenv('AZURE_DEPLOYMENT_NAME')
AZURE_EBD_DEPLOYMENT_NAME = os.getenv('AZURE_EBD_DEPLOYMENT_NAME')

API_TYPE = os.getenv('API_TYPE')

# 知识库、ai助手、云之家群关系的配置地址
CONFIG_PATH = "config/config.yml"

# 云之家通知地址
YUNZHIJIA_NOTIFY_URL = "https://www.yunzhijia.com/gateway/robot/webhook/send?yzjtype=0&yzjtoken={}"
# 云之家每张卡片消息最大图片数
MAX_IMG_NUM_IN_CARD_NOTICE = 5
# 云之家卡片消息模板id
CARD_NOTICE_TEMPLATE_ID = "64d08cb4e4b07ba2b112b395"


YUQUE_AUTH_TOKEN = "aAzViMlNLUtykug7vU5EnmQKvYn9DZGQICFmL3mB"
YUQUE_NAMESPACE = "nbklz3"
YUQUE_BASE_URL = "https://jdpiaozone.yuque.com/api/v2"
YUQUE_REQUEST_AGENT = "piaozone"
# assistant file最多文件数-1(要多留一个给faq.md)
ASSISTANT_FILE_NUM_LIMIT = 19


PIAOZONE_TOKEN_URL = "https://api-dev.piaozone.com/test/base/exception/login/token"
PIAOZONE_TOKEN_BODY = "U5/yFNQySPUsjrHqSDUFl58fJ7OxHT8W4KWJqK4tLd/ze1/IIFtmActgeM8VxT4uAUn4cW75sKLbaLXPOMFYTVQ+XJDmwosnJ+qsangGMujLo2S3zQqQ/AU8TUd7qgrdYdEKKBLoTIXeCoBA3jjH4u9h+PvFcwfQuSgJbmKwomc="
PIAOZONE_ADD_SOBOT_DOC_URL = "https://api-dev.piaozone.com/test/portal/m19/customer-service/sobot-doc/with-yuque-slug?access_token="
