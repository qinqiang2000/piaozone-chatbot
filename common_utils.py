import logging

from settings import CONFIG_PATH, YZJ_ASSISTANT_RELATE_PATH
import json
from bs4 import BeautifulSoup
import mammoth
import os
from pdf2docx.converter import Converter
from docx import Document


def get_assistant_id_by_yzj_token(yzj_token):
    with open(YZJ_ASSISTANT_RELATE_PATH, "r", encoding="utf-8") as file:
        return json.load(file)[yzj_token]


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


def convert_pdf_to_docx(pdf_path, filename):
    """
    将pdf文件转化为docx文件，并指定为filename
    :param pdf_path:
    :param filename:
    :return:
    """
    docx_filename = os.path.join(os.path.dirname(pdf_path), filename + '.docx')

    cv = Converter(pdf_path)
    cv.convert(docx_filename=docx_filename, ignore_page_error=False)
    cv.close()
    return docx_filename, count_words_in_docx(docx_filename)


def count_words_in_docx(docx_filename):
    doc = Document(docx_filename)
    total_words = 0
    for para in doc.paragraphs:
        total_words += len(para.text.split())
    return total_words


def get_docx_html_content(docx_file_path):
    """
    将docx文件转化为html内容,并返回
    :param docx_file_path:
    :return:
    """
    print(f"将文件{docx_file_path}转换为html内容")
    with open(docx_file_path, "rb", encoding="utf-8") as docx_file:
        result = mammoth.convert_to_html(docx_file)
        html_content = result.value  # 生成的 HTML 内容
        return html_content
