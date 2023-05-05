import logging
import os
from dotenv import load_dotenv

logging.basicConfig(format='[%(asctime)s %(filename)s:%(lineno)d] %(levelname)s: %(message)s', level=logging.INFO)

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
YUNZHIJIA_NOTIFY_URL = os.getenv('YUNZHIJIA_NOTIFY_URL')