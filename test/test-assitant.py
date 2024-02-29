import sys
import os
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root_dir)
import time
from io import StringIO

import traceback
import pandas as pd

from config.settings import *
from src.utils.logger import logger

def create_assistant():
    if USE_AZURE_OPENAI:
        from src.qa_assistant.azure_openai_assistant import Assistant
        assistant = Assistant(assistant_id=None, api_key=AZURE_OPENAI_API_KEY,
                              azure_endpoint=AZURE_OPENAI_ENDPOINT, api_version=OPENAI_API_VERSION,
                              deployment_name=OPENAI_DEPLOYMENT_NAME)
    else:
        from src.qa_assistant.openai_assistant import Assistant
        assistant = Assistant(assistant_id=None, api_key=OPENAI_API_KEY)
    name = "测试乐企"
    instructions = "你是中国税局乐企平台的智能客服。在回答问题时，注意底下每个括号内的所有名词，是同义词：\n（接入单位，直连单位）\n"\
                   "（稅编、税收分类编码、商品编码）\n要求：\n0.找到答案如果有关联图片，可以直接将图片链接代替图片。链接信息直接将链接输出，无需转化为markdown格式；"\
                   "\n1.请先从faq.md找答案，回答的内容可通过匹配该文件的“问题”，再直接将对应行的“答案”内容直接作为答案；\n2.如果找不到，找其他Markdown文件；注意：\n"\
                   "- 每个Markdown文件是由多个独立子文件组合而成；\n-Markdown内通过H1标签（‘#  ’）来区分不同文件；\n-不同子文件的内容不要混在一起做回答\n3.再找不到，请从互联网寻求答案；\n"\
                   "4.最后还是无法找到答案，请在回复的最后附加一句：【上述问题无法在标准知识库找到，具体请@张馨月】"
    assistant.create_assistant(name=name, instructions=instructions)
    return assistant
def get_assistant(assistant_id):
    if USE_AZURE_OPENAI:
        from src.qa_assistant.azure_openai_assistant import Assistant
        assistant = Assistant(assistant_id=assistant_id, api_key=AZURE_OPENAI_API_KEY,
                              azure_endpoint=AZURE_OPENAI_ENDPOINT, api_version=OPENAI_API_VERSION,
                              deployment_name=OPENAI_DEPLOYMENT_NAME)
    else:
        from src.qa_assistant.openai_assistant import Assistant
        assistant = Assistant(assistant_id=assistant_id, api_key=OPENAI_API_KEY)
    return assistant
def test_assistant():
    # 测试创建助手
    assistant = create_assistant()
    print(f"助手id：{assistant.assistant_id}")
    print(f"是否存在文件：{assistant.check_asst_file()}")
    try:
        # 测试添加文件
        file_path = "../docs/faq.md"
        assistant.create_file(file_path)
        # 测试对话
        session_id = "test_session_id"
        question = "怎么申请乐企？"
        answer = assistant.chat(session_id=session_id, content=question)
        print(f"问题：{question}\n答案：{answer}")
        question = "它的网址是什么？"
        answer = assistant.chat(session_id=session_id, content=question)
        print(f"问题：{question}\n答案：{answer}")
    except Exception as e:
        logger.error(f"测试助手出错：{e}.{traceback.format_exc()}")
    # 测试删除线程
    assistant.del_all_threads()
    # 测试删除文件
    assistant.empty_files()
    # 测试删除助手
    assistant.del_assistant()
if __name__ == '__main__':
    test_assistant()