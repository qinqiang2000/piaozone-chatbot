import logging
import re

from settings import CONFIG_PATH, YZJ_ASSISTANT_RELATE_PATH
import json
from bs4 import BeautifulSoup


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
