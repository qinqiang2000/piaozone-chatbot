from enum import Enum
from openai import OpenAI, AzureOpenAI

class ASSTType(int, Enum):
    """助手 类型"""
    NATIVE_ASST = 0
    ASST_WITH_SIMPLE_RAG = 1

class ASSTLLMType(str, Enum):
    """助手 llm 类型"""
    OPENAI = "openai"
    AZURE = "azure"

# Assistant类，用于处理openai的对话请求
class BaseAssistant:
    def __init__(self, assistant_id: str, assistant_config: dict):
        self.assistant_id = assistant_id
        self.setup_llmclient(assistant_config)
    def setup_llmclient(self, assistant_config: dict) -> None:
        self.llm_type = assistant_config["llm_option"]
        llm_config = assistant_config["llm_config"][self.llm_type]
        if self.llm_type == ASSTLLMType.OPENAI:
            self.client = OpenAI(api_key=llm_config["openai_api_key"])
            self.model_name = llm_config.get("model_name", None)
            self.llm_kwargs = llm_config.get("llm_kwargs", {})
        elif self.llm_type == ASSTLLMType.AZURE:
            self.client = AzureOpenAI(
                api_key=llm_config["azure_openai_api_key"],
                api_version=llm_config["openai_api_version"],
                azure_endpoint=llm_config["azure_openai_endpoint"]
            )
            self.model_name = llm_config.get("model_name", None)
            self.llm_kwargs = llm_config.get("llm_kwargs", {})
        else:
            raise ValueError(f"不支持的llm类型: {self.llm_type}")

    def chat(self, session_id: str, content: str) -> str:
        """
        用户发送消息，调用openai的接口，返回回复
        :param session_id: 由{app_type}~{robot_id}~{operatorOpenId}组成
        :param content:
        :return:
        """
        pass