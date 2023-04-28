import os
from itertools import chain
from collections import defaultdict
import pandas as pd
import json

from langchain.callbacks import CallbackManager
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.chat_models import ChatOpenAI, AzureChatOpenAI
from langchain import PromptTemplate, LLMChain
from langchain.prompts.chat import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    AIMessagePromptTemplate,
    HumanMessagePromptTemplate,
)
from langchain.schema import (
    AIMessage,
    HumanMessage,
    SystemMessage
)

from config import OPENAI_API_KEY, AZURE_BASE_URL, AZURE_DEPLOYMENT_NAME, AZURE_API_KEY

# set your openAI api key as an environment variable
os.environ['OPENAI_API_KEY'] = OPENAI_API_KEY

def split_docs():
    # 读取数据文件
    data = pd.read_excel('/Users/qinqiang02/Desktop/fpy知识库/GPT训练知识-知识库导出.xlsx')

    # 按照group_column分组
    grouped = data.groupby('分类')

    # 遍历每个分组，将其保存为CSV文件
    for group_name, group_data in grouped:
        group_name = group_name.replace('/', '_')
        group_data[['问题', '答案']].to_csv(f'/Users/qinqiang02/Desktop/fpy知识库/训练知识/{group_name}.csv',
                                            index=False)
# split_docs()

def detect_question(q):
    chat = AzureChatOpenAI(
            openai_api_base=AZURE_BASE_URL,
            openai_api_version="2023-03-15-preview",
            deployment_name=AZURE_DEPLOYMENT_NAME,
            openai_api_key=AZURE_API_KEY,
            openai_api_type="azure",
            streaming=True, callback_manager=CallbackManager([StreamingStdOutCallbackHandler()]),
            verbose=True, temperature=0
        )
    content = "请判断下面这句话是否一个完整的疑问句，如果是一个完整的疑问句，请输出：是；如果是陈述句或者名词，请输出：不是；如果是不完整的疑问句或者多条疑问句的组合，请输出修改成为完整疑问句的建议。"
    content = content + "\n" + q
    messages = [
        SystemMessage(content=content)
    ]
    return chat(messages).content


# 用gpt完善faq文档的问题一列，
def refine_faq_docs():
    # 读取数据文件
    df = pd.read_excel('/Users/qinqiang02/Desktop/fpy知识库/GPT训练知识-知识库导出.xlsx')

    questions_col = df['问题']
    new_col = []
    for question in questions_col:
        new_q = detect_question(question)
        new_col.append(new_q)

    # 将更新后的数据添加到新列“问题意见”中
    df.insert(1, '是否完整疑问句', new_col)

    # 保存到Excel文件
    df.to_excel('/Users/qinqiang02/Desktop/fpy知识库/new_filename.xlsx', index=False)

# refine_faq_docs()

# 处理语雀导出的文档列表
def load_json():
    doc_dict = {}
    with open('/Users/qinqiang02/Desktop/fpy知识库/GPT训练知识-知识库导出.json', 'r') as f:
        data = json.load(f)
        data = data['data']
        for item in data:
            doc_dict[item['title']] = item['slug']

    return doc_dict
# print(load_json())

# chat = ChatOpenAI(temperature=0)
# content = "请判断下面这句话是否一个完整的疑问句，如果是一个完整的疑问句，请输出：是；如果是陈述句或者名词，请输出：不是；如果是不完整的疑问句或者多条疑问句的组合，请输出修改成为完整疑问句的建议。"
# content = content + "\n" + "发票助手中的上传的附件excel表格能下载么"
# messages = [
#     SystemMessage(content=content)
# ]
# print(chat(messages))

def feq_sort(*lists):
    counter = defaultdict(int)
    for x in chain(*lists):
        counter[x] += 1
    return [key for (key, value) in
            sorted(counter.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)]


l = ["a", "b", "b", "b", "b", "a", "a", "c"]
# print(feq_sort(l))
