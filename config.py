import os

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', "")
INDEX_NAME = "fpy_operation_qa"
REDIS_URL = "redis://localhost:6379"
FAISS_DB_PATH = "db"

YUNZHIJIA_SEND_URL = os.environ.get('YUNZHIJIA_SEND_URL', "https://www.yunzhijia.com/gateway/robot/webhook/send"
                                                          "?yzjtype=0&yzjtoken=3fb3d03a665e4dfc955335d680410515")
