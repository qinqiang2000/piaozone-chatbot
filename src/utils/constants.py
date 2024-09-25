from enum import Enum

class QSource(int, Enum):
    """问题来源"""
    YUNZHIJIA = 0
    ZHICHI = 1

# ######## Tool Constants ########
# class ToolType(str, Enum):
#     """工具类型"""
#     SIMPLE_RAG = "simple_rag"
#
# ######## RAG Constants ########
# class RAGLLMType(str, Enum):
#     """rag llm类型"""
#     OPENAI = "openai"
#     AZURE = "azure"
#
# class RAGEmbeddingType(str, Enum):
#     """embedding 类型"""
#     AZURE_EMB = "azure_embedding"
#     OPENAI_EMB = "openai_embedding"