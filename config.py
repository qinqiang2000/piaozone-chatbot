import os
import logging

logging.basicConfig(format='[%(asctime)s %(filename)s:%(lineno)d] %(levelname)s: %(message)s', level=logging.INFO)

# openai
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', "")

#  azure openai
AZURE_BASE_URL = "https://kdtest.openai.azure.com/"
AZURE_API_KEY = os.environ.get('AZURE_API_KEY', "")  # 这里插入$做简单混淆，避免上传github删key
AZURE_DEPLOYMENT_NAME = "gpt35"
AZURE_EBD_DEPLOYMENT_NAME = "kdembedding"

INDEX_NAME = "fpy_operation_qa"
REDIS_URL = "redis://localhost:6379"
#

# YUNZHIJIA_NOTIFY_URL = os.environ.get('YUNZHIJIA_NOTIFY_URL', "https://www.yunzhijia.com/gateway/robot/webhook/send?yzjtype=0&yzjtoken=3fb3d03a665e4dfc955335d680410515")
YUNZHIJIA_NOTIFY_URL = os.environ.get('YUNZHIJIA_NOTIFY_URL', "https://www.yunzhijia.com/gateway/robot/webhook/send?yzjtype=0&yzjtoken=33604eb24ce34ee8a1a8577b4d992ac7")

FPY_KEYWORDS = ["发票", "乐企", "税局", "星瀚", "星辰", "星空", "EAS", "KIS", "K3", "开票", "收票", "影像", "档案", "AWS",
                "我家云", "管易云", "精斗云", "票省事", "分机盘", "金蝶", "软证书"]