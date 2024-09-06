from enum import Enum
from openai import OpenAI, AzureOpenAI, AsyncOpenAI, AsyncAzureOpenAI

class ASSTType(str, Enum):
    """助手 类型"""
    OPENAI_ASSISTANT = "openai_assistant"


# Assistant类，用于处理openai的对话请求
class BaseAssistant:
    def __init__(self, assistant_id: str, assistant_config: dict, llm_configs: dict):
        self.assistant_id = assistant_id
        self.set_client(assistant_config, llm_configs)
    def set_client(self, assistant_config: dict, llm_configs: dict) -> None:
        self.llm_type = assistant_config.get("llm_option", "openai")
        llm_configs = llm_configs[self.llm_type]
        if self.llm_type == "openai":
            self.client = OpenAI(api_key=llm_configs.get("api_key"))
            self.async_client = AsyncOpenAI(api_key=llm_configs.get("api_key"))
            self.model_name = assistant_config.get("llm_model_name")
            self.llm_kwargs = assistant_config.get("llm_kwargs", {})
        elif self.llm_type == "azure_openai":
            self.client = AzureOpenAI(
                api_key=llm_configs.get("api_key"),
                api_version=llm_configs.get("api_version"),
                azure_endpoint=llm_configs.get("endpoint")
            )
            self.async_client = AsyncAzureOpenAI(
                api_key=llm_configs.get("api_key"),
                api_version=llm_configs.get("api_version"),
                azure_endpoint=llm_configs.get("endpoint")
            )
            self.model_name = None
            for deployment_name, model_name in llm_configs.get("model_map_table", {}).items():
                if model_name == assistant_config.get("llm_model_name"):
                    self.model_name = deployment_name
                    break
            self.llm_kwargs = llm_configs.get("llm_kwargs", {})
        else:
            raise ValueError(f"不支持的llm类型: {self.llm_type}")

    def chat(self, session_id: str, content: str) -> str:
        """
        用户发送消息，调用openai的接口，返回回复
        :param session_id:
        :param content:
        :return:
        """
        pass