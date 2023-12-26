import logging
import re

from config.settings import CONFIG_PATH, YZJ_ASSISTANT_RELATE_PATH
import json
from bs4 import BeautifulSoup
import pandas as pd
import openpyxl
import os
import zipfile
import shutil
import yaml


config_path = "config/config_yq.yml"
# 工程路径 + config/config_yq.yml
config_path = os.path.join(os.path.dirname(__file__), config_path)
config_data = yaml.load(open(config_path, 'rb'), Loader=yaml.Loader)


# 从云之家群token获取assistant_id
def get_assistant_id_by_yzj_token(yzj_token):
    for repo, dirs in config_data.items():
        for info in dirs.values():
            if yzj_token in info['yzj_token']:
                return info['gptAssistantId']
    return None


# 从云之家群token获取语雀知识库id、分组title和assistant_id
def get_info_by_yzj_token(yzj_token):
    repo, toc_title = get_yq_info_by_yzj_token(yzj_token)
    asst_id = get_assistant_id_by_yzj_token(yzj_token)

    return repo, toc_title, asst_id


# 从云之家群token获取语雀知识库id和分组id
def get_yq_info_by_yzj_token(yzj_token):
    for repo, dirs in config_data.items():
        for toc_title, info in dirs.items():
            if yzj_token in info['yzj_token']:
                return repo, toc_title
    return None, None


def get_config(assistant_id=None, key=None):
    with open(CONFIG_PATH, "r", encoding="utf-8") as file:
        if not assistant_id:
            # 不传assistant_id则表示获取文档所有json
            return json.load(file)
        if key:
            return json.load(file)[assistant_id][key]
        else:
            return json.load(file)[assistant_id]


def save_config(assistant_id, key, content):
    raw_config = get_config()
    raw_config[assistant_id][key] = content
    with open(CONFIG_PATH, "w", encoding="utf-8") as file:
        json.dump(raw_config, file, indent=4)
    logging.info(f"保存文件config.json {raw_config}")


def clear_css_code(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')

    for style_tag in soup.find_all('style'):
        style_tag.decompose()

    for tag in soup.find_all(style=True):
        del tag['style']

    for tag in soup.find_all(class_=True):
        del tag['class']
    return soup.prettify()


def remove_html_tags(text):
    # 定义HTML标签的正则表达式
    html_tags_pattern = re.compile(r'<[^>]+>')

    # 使用正则表达式移除所有HTML标签
    return html_tags_pattern.sub('', text)


def parse_img_urls(text):
    """
    截取所有图片url（后缀为jpg|jpeg|png|gif）
    :param text:
    :return:
    """
    img_urls = re.findall(
        "http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+\.(?:jpg|jpeg|png|gif)",
        text)
    return img_urls


def zip_folder(folder_path):
    """
    创建一个ZipFile对象，并指定要输出的ZIP文件
    :param folder_path:
    :return: 最终zip文件绝对路径
    """
    # 以文件夹名作为输出zip文件名
    output_zip_file = folder_path + ".zip"
    with zipfile.ZipFile(output_zip_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # 遍历目录树并添加文件到zip
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                # 创建文件的完整路径
                full_path = os.path.join(root, file)
                # 计算在ZIP文件中的路径
                relative_path = os.path.relpath(full_path, folder_path)
                # 添加文件到zip
                zipf.write(full_path, relative_path)

    logging.info(f'文件夹 "{folder_path}" 已被压缩为 "{output_zip_file}"')
    # 删除原始文件夹
    shutil.rmtree(folder_path)
    return output_zip_file


def excel_sheets_to_markdown_and_zip(excel_file_path):
    """
    将指定excel文件的所有sheet(不包括隐藏的)转化为以【excel文件名-sheet名】为名称的markdown文件，并压缩为一个zip包
    :param excel_file_path:
    :return: 结果zip的绝对路径
    """
    # 使用openpyxl加载Excel文件
    workbook = openpyxl.load_workbook(excel_file_path)
    # 以excel文件名为输出文件夹
    output_folder = os.path.splitext(os.path.abspath(excel_file_path))[0]
    # 检查输出文件夹是否存在，如果不存在，则创建
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # 遍历所有工作表
    for sheet_name in workbook.sheetnames:
        # 获取工作表对象
        worksheet = workbook[sheet_name]
        # 检查工作表是否隐藏
        if worksheet.sheet_state == 'visible':
            # 读取工作表
            df = pd.read_excel(excel_file_path, sheet_name=sheet_name, na_filter=False)
            # 检查并替换以"Unnamed"开头的列名
            df.columns = [col if not col.startswith('Unnamed') else '' for col in df.columns]
            # 将DataFrame转换为Markdown格式的字符串
            markdown_str = df.to_markdown(index=False)
            excel_file_name = os.path.splitext(os.path.basename(excel_file_path))[0]
            # Markdown文件的路径
            markdown_file_path = os.path.join(output_folder, f'{excel_file_name + "-" + sheet_name}.md')
            # 将Markdown字符串写入文件
            with open(markdown_file_path, 'w', encoding='utf-8') as file:
                file.write(markdown_str)
            logging.info(f'Markdown文件已生成：{markdown_file_path}')
    # 删除excel文件
    os.remove(excel_file_path)
    return zip_folder(output_folder)


def is_xlsx_file(file_path):
    # 获取文件扩展名
    _, ext = os.path.splitext(file_path)
    # 检查扩展名是否为Excel格式
    return ext.lower() == '.xlsx'
