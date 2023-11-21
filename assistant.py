import logging

import openai
from openai import OpenAI
import pandas as pd
from io import StringIO

FAQ_PATH = "../data/faq.md"

# Assistant类，用于处理openai的请求
class Assistant:
    def __init__(self, assistant_id, api_key=None, base_url=None, ):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.assistant_id = assistant_id
        self.run = None
        self.thread_map = {}   # 不能指定id创建thread，所以需要一个map来存储session id和thread_id的映射关系

        # 这个需要持久化读取和保存，用于记录上一次的faq文件id
        self.last_faq_file_id = "file-UDl2X81HQuv9tVtWZTgDzNSy"

    def add_faq(self, question, answer):
        logging.info(f"增加新语料：{question} --> {answer}")
        add_one_row(FAQ_PATH, question, answer)

        # 删除上一次在assistant里面的faq文件
        try:
            self.client.beta.assistants.files.delete(
                assistant_id=self.assistant_id,
                file_id=self.last_faq_file_id
            )
        except openai.NotFoundError as e:
            logging.error(f"不存在：{e}")

        # 上传新文件
        file = self.client.files.create(
            file=open(FAQ_PATH, "rb"),
            purpose='assistants'
        )

        self.last_faq_file_id = file.id

        # 加载到新文件到assistant
        assistant_file = self.client.beta.assistants.files.create(
            assistant_id=self.assistant_id,
            file_id=self.last_faq_file_id
        )

        if assistant_file:
            logging.info(f"增加新文件：{assistant_file}")

    def chat(self, session_id, content):
        # 如果session_id不存在，创建一个新的thread;
        if session_id not in self.thread_map:
            thread = self.client.beta.threads.create()
            self.thread_map[session_id] = thread.id

        thread_id = self.thread_map.get(session_id)

        self.client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=content
        )

        self.run = self.client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=self.assistant_id
        )

    def get_answer(self, session_id):
        thread_id = self.thread_map.get(session_id)
        if not thread_id:
            return None

        run = self.client.beta.threads.runs.retrieve(
            thread_id=thread_id,
            run_id=self.run.id
        )

        if run.status != "completed":
            logging.debug(f"[{session_id}]: {run.status}")
            return None

        messages = self.client.beta.threads.messages.list(thread_id=thread_id, limit=1)
        return messages.data[0].content[0].text


# 增加一行到faq.md文件中
def add_one_row(file_path, question, answer):
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
    logging.info(df.iloc[-1])

    # 将修改后的 Markdown 表格写回到原文件
    md_table_modified = df.to_markdown(index=False)
    with open(file_path, 'w') as file:
        file.write(md_table_modified)

    logging.info("Markdown 文件已更新并保存。")