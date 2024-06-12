# import os
# from dotenv import load_dotenv
# load_dotenv(override=True)
#
# ASSISTANT_WITH_SIMPLE_RAG_CONFIG = {
#     "asst_type": ASSTType.ASST_WITH_SIMPLE_RAG,
#     "llm_option": "openai",  # 详见 src/qa_assistant/base_assistant.py的 ASSTLLMType, options: "openai", "azure"
#     "llm_config": {
#         "openai": {
#             "openai_api_key": os.getenv("OPENAI_API_KEY"),
#             "model_name": "gpt-4-1106-preview"
#         },
#         "azure": {
#             "azure_openai_api_key": os.getenv("AZURE_OPENAI_API_KEY"),
#             "openai_api_version": os.getenv("OPENAI_API_VERSION"),
#             "azure_openai_endpoint": os.getenv("AZURE_OPENAI_ENDPOINT"),
#             "model_name": os.getenv("OPENAI_DEPLOYMENT_NAME")
#         }
#     },
#     "tool_config": [{
#         "tool_type": "rag",  # 详见 src/tools/__init__.py, options: "simple_rag"
#         "tool_config": SIMPLE_RAG_CONFIG
#     }],
#
#
# }
# #simple RAG配置
# ## 包含 rag_option,chat_config和docdb_config
# ## chat_config: 问答助手配置，包含llm_option, llm_config
# ## docdb_config: 文档库配置，包含embedding_config, connection_args, doc_top_k, faq_top_k, chunk_size, chunk_overlap
# SIMPLE_RAG_CONFIG = {
#     "rag_option": "simple_rag",  # 详见 src/tools/rag/base_rag.py 的 RAGType, options: "simple_rag"
#     "chat_config": {
#         "llm_option": "azure",  # 详见 src/tools/rag/base_rag.py 的 RAGLLMType, options: "openai", "azure"
#         "llm_config": {
#             "openai": {
#                 "model_name": "gpt-4-1106-preview",
#                 "openai_api_key": os.getenv("OPENAI_API_KEY"),
#                 "llm_kwargs": {
#                     "temperature": 0
#                 }
#             },
#             "azure": {
#                 "model_name": os.getenv("OPENAI_DEPLOYMENT_NAME"),
#                 "azure_openai_api_key": os.getenv("AZURE_OPENAI_API_KEY"),
#                 "openai_api_version": os.getenv("OPENAI_API_VERSION"),
#                 "azure_openai_endpoint": os.getenv("AZURE_OPENAI_ENDPOINT"),
#                 "llm_kwargs": {
#                     "temperature": 0
#                 },
#             }
#         }
#     },
#     "docdb_config": {
#         "embedding_config": {
#             "model_option": "azure_embedding",  # 详见 src/tools/rag/base_rag.py 的 RAGEmbeddingType, options: "azure_embedding", "openai_embedding"
#             "openai_embedding": {
#                 "model_name": "text-embedding-ada-002",
#                 "openai_api_key": os.getenv("OPENAI_API_KEY"),
#             },
#             "azure_embedding": {
#                 "model_name": os.getenv("OPENAI_EMBEDDING_DEPLOYMENT_NAME"),
#                 "azure_openai_api_key": os.getenv("AZURE_OPENAI_API_KEY"),
#                 "openai_api_version": os.getenv("OPENAI_API_VERSION"),
#                 "azure_openai_endpoint": os.getenv("AZURE_OPENAI_ENDPOINT")
#             }
#         },
#         "connection_args": {
#             "url": os.getenv("WEAVIATE_URL")
#         },
#         "doc_top_k": 20,  # 文档查询返回的最大数量
#         "faq_top_k": 20,  # faq查询返回的最大数量
#         "chunk_size": 800,  # 文档分块大小
#         "chunk_overlap": 400,  # 文档分块重叠大小
#     }
# }
