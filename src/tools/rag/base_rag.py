
from enum import Enum

######## RAG Constants ########
class RAGType(str, Enum):
    """rag 类型"""
    SIMPLE_RAG = "simple_rag"
class RAGLLMType(str, Enum):
    """rag llm类型"""
    OPENAI = "openai"
    AZURE = "azure"

class RAGEmbeddingType(str, Enum):
    """embedding 类型"""
    AZURE_EMB = "azure_embedding"
    OPENAI_EMB = "openai_embedding"

class BaseRAGTool:
    """ RAG工具 """
    name = "question_answer"
    tool_schema = {
        "type": "function",
        "function": {
            "name": "question_answer",
            "description": "在知识库中查询问题的答案",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "用户的问题",
                    }
                },
                "required": ["question"]
            }
        }
    }

    def __init__(self, rag_config: dict):
        self._validate_rag_type(rag_config)
        self.setup_configs(rag_config)

    def setup_configs(self, rag_config: dict):
        self.chat_config = rag_config["chat_config"]
        self.docdb_config = rag_config["docdb_config"]
    def _validate_rag_type(self, rag_config: dict):
        """
        验证配置
        """
        if rag_config["rag_option"] not in list(RAGType):
            raise ValueError(f"使用了未支持的 RAG tool type: {rag_config['rag_option']}")

    def __call__(self, question: str):
        return self.invoke_functions(query=question)

    def invoke_functions(self, query: str):
        """
        :param query: 问题
        :return: the result of the function
        """
        pass


