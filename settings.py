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

# 云之家通知地址
YUNZHIJIA_NOTIFY_URL = "https://www.yunzhijia.com/gateway/robot/webhook/send?yzjtype=0&yzjtoken={}"

# 机器人助手id
LEQI_ASSISTANT_ID = 'asst_G5t60WEtbD9ygU5n2Ol727N6'

YUQUE_AUTH_TOKEN = "aAzViMlNLUtykug7vU5EnmQKvYn9DZGQICFmL3mB"
YUQUE_NAMESPACE = "nbklz3"
YUQUE_BASE_URL = "https://jdpiaozone.yuque.com/api/v2"
YUQUE_REQUEST_AGENT = "piaozone"
ASSISTANT_FILE_NUM = 9
SINGLE_DOC_END = "========================================《{}》结尾，字数：{}============================================="

CONFIG_PATH = "./config.json"
YZJ_ASSISTANT_RELATE_PATH = "./yzj_assistant_relate.json"
FAQ_DOC_END = "**该文档由系统自动生成，文档每天都会覆盖更新，禁止在此编辑。若想变更内容，请移步**[**https://tax-test.piaozone.com/operation-monitor/public/no-login/sobot-docs**](https://tax-test.piaozone.com/operation-monitor/public/no-login/sobot-docs)**操作。**"
