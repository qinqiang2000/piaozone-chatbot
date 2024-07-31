import os,sys
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root_dir)

from src.utils.database import SQLDatabase,Base,FAQ
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy import and_
import datetime
import requests
import re


DB_CONFIG = {
    "user": "root",
    "password": "123456",
    "host": "localhost",
    "port": "3306",
    "db": "test", #db 后续改成服务器db
    "charset": "utf8"
}
database = SQLDatabase(**DB_CONFIG)

'''
class FAQ(Base):
    __tablename__ = 'FQA_record'
    id = Column(Integer, primary_key=True, autoincrement=True)
    topic_name = Column(Text, nullable=False)
    question = Column(LONGTEXT, nullable=False, unique=True)
    answer = Column(LONGTEXT, nullable=False)
    has_answer = Column(Text, nullable=False)
    asker = Column(Text, nullable=False)
    entry_time = Column(DateTime, default=datetime.datetime.now)

'''
# 录入信息到数据库
def insert_faq_to_db(table_class, topic_name, question, answer,  asker):
    """
    将faq数据录入数据库
    """
    has_answer = '是'
    has_answer_key = ["上述问题无法在标准知识库中找到答案", "在标准知识库中未能找到明确答案", "上述问题无法在标凈知识库找到答案", "上述问题无法在标净知识库找到答案"]
    if any(phrase in answer for phrase in has_answer_key):
        has_answer = '否'
    #database.create_table(table_class)
    data = {'topic_name': topic_name, 'question': question, 'answer': answer, 'has_answer': has_answer, 'asker': asker}
    database.insert_data(table_class, data)


def extract_and_update_yuque(table_class, yuque_url, yuque_headers):
    """
    将前一天的所有数据更新到语雀文档中（因为设定每天2点更新，所以需要更新前一天的）
    """
    #获取url现有数据
    try:
        response = requests.get(yuque_url, headers=yuque_headers)
        response.raise_for_status()
        existing_content = response.json()['data']
        existing_body = existing_content['body']
        print(existing_body)
        update_time = existing_content.get('updated_at')
    except requests.exceptions.RequestException as e:
        print(f"获取现有数据失败：{e}")


    #从数据库获取前一天0点到今天0点的数据
    now = datetime.datetime.now()
    #yesterday = datetime.datetime.combine(now.date() - datetime.timedelta(days=1), datetime.time(0, 0))
    today = datetime.datetime.combine(now.date(), datetime.time(14, 0))
    filter_cond = and_(table_class.entry_time >= update_time, table_class.entry_time <= today)
    extract_data = database.complex_query_data(table_class,filter_cond)

    results = [] #储存得到的数据
    for result in extract_data:
        res = {'id':result.id, 'topic_name': result.topic_name,'question': result.question, 'answer': result.answer,
               'has_answer':result.has_answer,'asker': result.asker,'entry_time':result.entry_time}
        #print(res)
        results.append(res)


    header = '| 序号 | 产品线 | 问题来源编号 | 问题模块 | 问题等级 | 问题描述 | GPT参考答案 | 知识库是否存在答案 | 最终回复答案 | 提问人 | 解答人 | 录入时间 |\n '
    header += '|---|---|---|---|---|---|---|---|---|---|---|---|\n'
    new_content = ''
    for item in results:
        format_ans = item['answer'].replace('\n\n', '<br />')
        row = f"| {item['id']} | {item['topic_name']} | <br /> | <br /> | <br /> | {item['question']} | {format_ans} | {item['has_answer']} | <br /> | {item['asker']} | <br /> | {item['entry_time']} |\n"
        new_content += row

    # 如果body不为空，加上新的数据
    if existing_body.strip():
        #print('body不为空')
        update_content_body = existing_body + new_content
    else:
        #print('body为空')
        update_content_body = header + new_content
    #print(update_content_body)

    update_content = {
        'title': 'FAQ信息',
        'format': 'markdown',
        'body': update_content_body, #
        'public': 2
    }
    # 发送 PUT 请求更新数据
    try:
        #response = requests.put(yuque_url, headers=yuque_headers, json=update_content)
        response.raise_for_status()
        print("数据更新成功！")
    except requests.exceptions.RequestException as e:
        print(f"数据更新失败：{e}")


def clear_website(yuque_url, yuque_headers):
    header = '| 序号 | 产品线 | 问题来源编号 | 问题模块 | 问题等级 | 问题描述 | GPT参考答案 | 知识库是否存在答案 | 最终回复答案 | 提问人 | 解答人 | 录入时间 |\n '
    header += '|---|---|---|---|---|---|---|---|---|---|---|---|\n'
    update_content = {
        'title': 'FAQ信息',
        'format': 'markdown',
        'body': header,
        'public': 2
    }
    try:
        response = requests.put(yuque_url, headers=yuque_headers, json=update_content)
        response.raise_for_status()
        print("数据更新成功！")
    except requests.exceptions.RequestException as e:
        print(f"数据更新失败：{e}")


if __name__ == '__main__':
    # 在这里测试

    table_class = FAQ
    #database.delete_data(table_class, {'id': 1})
    topic_name ="测试3"
    question = "数电票火车票是否支持查验"
    answer =' 数电票火车票是支持查验的。根据相关文档，发票云能够实现对火车票的识别和查验服务，具体支持的票据种类包括火车票以及其他类型的票据。'
    asker = "test2"
    #insert_faq_to_db(table_class, topic_name, question, answer,  asker)
    yuque_url = "https://jdpiaozone.yuque.com/api/v2/repos/nbklz3/kro38t/docs/gx8rugmggonygnve" #后续需要改，可能是多个拼接
    yuque_headers = {
            "X-Auth-Token": "aAzViMlNLUtykug7vU5EnmQKvYn9DZGQICFmL3mB",
            "User-Agent": "piaozone"
        }
    clear_website(yuque_url, yuque_headers)
    #extract_and_update_yuque(table_class, yuque_url, yuque_headers)



