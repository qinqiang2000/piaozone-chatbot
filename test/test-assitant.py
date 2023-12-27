import time

from assistant import Assistant
from openai import OpenAI
import pandas as pd
from io import StringIO
from config.settings import *

load_dotenv(override=True)

client = OpenAI()

LEQI_ASSISTANT_ID="asst_G5t60WEtbD9ygU5n2Ol727N6"
file_path = '../data/faq.md'  # 替换为你的文件路径
FAQ_FILE_ID = "file-oVYtNglhudbLVCSNuO5EvTf8"
leqi_assistant = Assistant(LEQI_ASSISTANT_ID)

def tetst_assistant_add_faq():
    leqi_assistant.add_faq("问题：乐企联用和通用预计什么时候开通", "答案：预计2024年12月")

tetst_assistant_add_faq()

def test_file(question, answer):
    with open(file_path, 'r') as file:
        md_content = file.read()

    # 将 Markdown 表格内容转换为 StringIO 对象
    md_table = StringIO(md_content)

    # 使用 pandas 读取表格，假设表格用 '|' 分隔，并跳过格式行
    df = pd.read_csv(md_table, sep='|', skiprows=[1])

    # 删除多余的空白列
    df = df.drop(columns=[df.columns[0], df.columns[-1]])

    # 增加一行，第一列的值是最后一行第一列的值 + 1
    last_row = df.iloc[-1]
    new_row = last_row.copy()
    new_row[df.columns[0]] = last_row[df.columns[0]] + 1
    new_row[df.columns[1]] = question
    new_row[df.columns[2]] = answer
    df = df._append(new_row, ignore_index=True)
    print(df.iloc[-1])

    # 将修改后的 Markdown 表格写回到原文件
    md_table_modified = df.to_markdown(index=False)
    with open(file_path, 'w') as file:
        file.write(md_table_modified)


def test_add_file():
    test_file("公有云环境可以申请乐企吗", "可以，但要排队很久")

def test_del_file():

    deleted_assistant_file = client.beta.assistants.files.delete(
        assistant_id=LEQI_ASSISTANT_ID,
        file_id=FAQ_FILE_ID
    )
    print(deleted_assistant_file)


def test_assistant():
    thread_id = 'fpy-abc'

    # 创建一个Assistant类，用于处理openai的请求
    yzj = Assistant('asst_G5t60WEtbD9ygU5n2Ol727N6')

    yzj.chat(thread_id, "怎么申请乐企？")

    while True:
        time.sleep(2)
        answer = yzj.get_answer('fpy-abc')
        if answer:
            print(answer)
            break

    yzj.chat('fpy-abc', "它的网址是什么？")

    while True:
        time.sleep(2)
        answer = yzj.get_answer('fpy-abc')
        if answer:
            print(answer)
            break