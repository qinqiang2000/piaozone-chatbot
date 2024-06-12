"""
GPT Assistant writer模块，提供同步数据到GPT Assistant的功能
"""

import traceback

from src.utils.logger import logger
from src.qa_assistant.base_assistant import BaseAssistant

class OpenAIAsstWriter:
    """适用于OpenAI Assistant/ Azure OpenAI Assistant的writer模块,Assistant本身需要有empty_files，create_vs函数"""

    def __call__(self, docs_path: list, assistant: BaseAssistant) -> bool:
        # 清空原有数据
        if not assistant.empty_files():
            return False
        if not docs_path:
            logger.info(f"[asst_id={assistant.assistant_id}]：没有需要同步的数据")
            return True
        if not assistant.create_vs(docs_path):
            return False
        logger.debug(f"[asst_id={assistant.assistant_id}]：同步数据到gpt assistant成功。 ")
        return True