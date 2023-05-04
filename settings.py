import logging
import os
from dotenv import load_dotenv


load_dotenv(override=True)

logging.basicConfig(format='[%(asctime)s %(filename)s:%(lineno)d] %(levelname)s: %(message)s', level=logging.INFO)

# openai
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# azure openai
AZURE_API_KEY = os.getenv('AZURE_API_KEY')
AZURE_BASE_URL = "https://kdtest.openai.azure.com/"
AZURE_DEPLOYMENT_NAME = "gpt35"
AZURE_EBD_DEPLOYMENT_NAME = "kdembedding"

# INDEX_NAME = "fpy_operation_qa"

# 云之家通知地址
YUNZHIJIA_NOTIFY_URL = os.getenv('YUNZHIJIA_NOTIFY_URL')

FPY_KEYWORDS = ["发票", "乐企", "税局", "星瀚", "星辰", "星空", "EAS", "KIS", "K3", "开票", "收票", "影像", "档案", "AWS",
                "我家云", "管易云", "精斗云", "票省事", "分机盘", "金蝶", "软证书"]