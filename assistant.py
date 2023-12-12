import openai
from openai import OpenAI
import pandas as pd
from io import StringIO

from common_utils import *
import yuque_utils
import settings

FAQ_PATH = "./data/faq.md"


# Assistant类，用于处理openai的请求
class Assistant:
    def __init__(self, assistant_id, api_key=None, base_url=None, ):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.assistant_id = assistant_id
        self.run = None
        self.thread_map = {}  # 不能指定id创建thread，所以需要一个map来存储session id(robot id + "~" + operatorOpenId)和thread_id的映射关系

    def add_faq(self, question, answer, submitter):
        logging.info(f"{submitter} 增加新语料：{question} --> {answer}")

        md_content = add_one_row(self.assistant_id, question, answer)
        with open(FAQ_PATH, "w", encoding="utf-8") as file:
            file.write(md_content)

        # 删除上一次在assistant里面的faq文件
        last_faq_file_id = get_config(self.assistant_id, "last_faq_file_id")
        self.del_file(last_faq_file_id)
        # 加载到新文件到assistant
        assistant_file = self.create_file(FAQ_PATH)

        # 保存新文件id
        save_config(self.assistant_id, "last_faq_file_id", assistant_file.id)

        if assistant_file:
            logging.info(f"增加新文件：{assistant_file}")

    def chat(self, session_id, content):
        """
        :param session_id: 由{robot_id}~{operatorOpenId}组成
        :param content:
        :return:
        """
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
        """
        :param session_id:由{robot_id}~{operatorOpenId}组成
        :return:
        """
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

    def list_files(self):
        assistant_files = self.client.beta.assistants.files.list(
            assistant_id=self.assistant_id
        )
        return assistant_files

    def create_file(self, file_path):
        # 上传新文件
        with open(file_path, "rb") as f:
            file = self.client.files.create(
                file=f,
                purpose='assistants'
            )
            # 加载到新文件到assistant
            assistant_file = self.client.beta.assistants.files.create(
                assistant_id=self.assistant_id,
                file_id=file.id
            )
            return assistant_file

    def del_file(self, file_id):
        try:
            deleted_assistant_file = self.client.beta.assistants.files.delete(
                assistant_id=self.assistant_id,
                file_id=file_id
            )
            file = self.client.files.delete(file_id)
            logging.info(f"删除上一次的文件：{deleted_assistant_file} {file}")
            return deleted_assistant_file
        except openai.NotFoundError as e:
            logging.error(f"不存在：{e}")


# 增加一行到faq.md文件中
def add_one_row(assistant_id, question, answer):
    # 根据配置获取关联语雀的第一个faq文档内容
    yuque_relate_and_faq_slug = get_config(assistant_id, "yuque_relate_and_faq_slug")
    if not len(yuque_relate_and_faq_slug):
        raise Exception("语雀关联yuque_relate_and_faq_slug配置为空，请检查")
    repo_and_toc_uuid = next(iter(yuque_relate_and_faq_slug))
    repo = repo_and_toc_uuid.split("/")[0]
    faq_slugs = yuque_relate_and_faq_slug[repo_and_toc_uuid]
    # 将新增问答同步到faq_slugs数组的第一个slug中
    yuque_doc = yuque_utils.get_yuque_doc(repo, faq_slugs[0])

    # 去掉文档末尾的说明
    md_content = yuque_doc["body"].replace(settings.FAQ_DOC_END, "")
    # 将 Markdown 表格内容转换为 StringIO 对象
    md_table = StringIO(md_content)
    # 使用 pandas 读取表格，假设表格用 '|' 分隔，并跳过格式行
    df = pd.read_csv(md_table, sep='|', skiprows=[1])

    # 删除多余的空白列
    df = df.drop(columns=[df.columns[0], df.columns[-1]])

    # 增加一行，第一列的值是最后一行第一列的值 + 1
    last_row = df.iloc[-1]
    new_row = last_row.copy()
    new_row[df.columns[0]] = question
    new_row[df.columns[1]] = answer
    df = df._append(new_row, ignore_index=True)
    logging.info(df.iloc[-1])

    # 将修改后的 Markdown 表格写回到原文件
    md_table_modified = df.to_markdown(index=False)
    md_table_modified += "\n" + settings.FAQ_DOC_END
    yuque_utils.update_yuque_doc(repo, yuque_doc, md_table_modified, "markdown")
    # 同步到运营管理平台
    try:
        yuque_utils.add_piaozone_question(repo, faq_slugs[0], question, answer)
    except Exception as e:
        logging.error(f"添加faq词条{question} {answer}时，同步到运营管理平台{repo}/{faq_slugs[0]}出错。原因：{e}")
    logging.info("Markdown 文件已更新并保存。")
    return md_table_modified
