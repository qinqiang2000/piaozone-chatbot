"""
数据处理相关的函数
"""
import re
import requests
import pandas as pd
import pypinyin

from src.utils.logger import logger

## pandas dataframe process
def clear_pd_nan(df):
    # 删除df的空行和空列
    df.replace('', pd.NA, inplace=True)
    df.dropna(how='all', axis=0, inplace=True)
    df.dropna(how='all', axis=1, inplace=True)
    df.replace(pd.NA, '', inplace=True)
    df.reset_index(drop=True, inplace=True)
def pd_table_to_dict(df, has_header=True):
    if not has_header:
        # 如果没有表头，将第一行设置为表头
        col_name = list(df.loc[0])
    else:
        col_name = list(df.columns)
    # 1. 去除列名两端的空格
    col_name = [str(name).strip() for name in col_name]
    # 2. 替换空列名为"Unnamed"
    col_name = [name if name.strip() else "Unnamed" for name in col_name]
    # 3. 处理重复列名
    col_count = dict()
    new_col_name = []
    for name in col_name:
        if name in col_count:
            new_col_name.append(f"{name}_{col_count[name]}")
            col_count[name] += 1
        else:
            new_col_name.append(name)
            col_count[name] = 1
    df.columns = new_col_name
    if not has_header:
        df = df.iloc[1:]
    return df.to_dict(orient="records")

## process mardown
def md_basic_process(text):
    """
    基本的markdown文本处理
    """
    # 去除不可见字符
    text = re.sub(r'[\x00\x05]', '', text)
    text = re.sub(r'\xa0', '', text)
    # 将粗体转换为普通字体
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    # 将斜体转换为普通字体
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)
    # 将删除线转换为普通字体
    text = re.sub(r'~~(.+?)~~', r'\1', text)
    # 去除语雀导出的<a>标签
    text = re.sub(r"<a name=\".*?\"></a>\n", "", text)
    return text
def yq_md_text_process(text):
    """
    特定于yuque markdown的文本处理
    """
    # 去除"\<br \/\>"
    text = re.sub(r"\<br \/\>", "\n", text)
    # 去除连续换行
    text = re.sub("\n+", "\n", text)
    return text

def separate_markdown_text_table(text):
    """
    将markdown文本中的文本和表格分离
    """
    current_data = []
    is_table = False
    for line in text.split("\n"):
        if re.search(r"^\|.*\|$", line):
            if is_table:
                current_data[-1]["text"].append(line)
            else:
                current_data.append({"text": [line], "type": "table"})
                is_table = True
        else:
            if is_table:
                current_data.append({"text": [line], "type": "text"})
                is_table = False
            else:
                if current_data and current_data[-1]["type"] == "text":
                    current_data[-1]["text"].append(line)
                else:
                    current_data.append({"text": [line], "type": "text"})
    check_table_format(current_data)
    return current_data

def check_table_format(tables):
    """
    检查表格格式是否正确
    """
    for table in tables:
        if table["type"] == "table":
            # 检查表格每一行的列数是否一致
            col_count = len(table["text"][0].split("|")) - 2
            for row in table["text"]:
                if len(row.split("|")) - 2 != col_count:
                    table["type"] = "text"
                    break
            if table["type"] == "table":
                if len(table["text"]) < 2:
                    table["type"] = "text"
                    continue

                # 检查第二行是否为分隔符行
                separator_valid = True
                for sep in table["text"][1].strip("|").split("|"):
                    if sep.strip() != "---":
                        separator_valid = False
                        break
                if not separator_valid:
                    table["type"] = "text"

def process_topic_name(topic_name, max_length=60):
    """
    处理专题名称，转换为合法的专题名称
    :param topic_name: 专题名称
    :param max_length: 最大字符长度
    :return: 处理后的专题名称
    """
    # 1. 汉字转拼音
    full_result = ''
    for py in pypinyin.pinyin(topic_name, style=pypinyin.NORMAL):
        full_result += ''.join(py)
    full_result = full_result.lower()

    # 2.如果处理后的名称超出指定长度，仅保留拼音首字母
    if len(full_result) > max_length:
        s = ''
        for py in pypinyin.pinyin(topic_name, style=pypinyin.FIRST_LETTER):
            s += ''.join(py)
        s = s.lower()
    else:
        s = full_result
    # 使用正则表达式替换掉所有非法字符
    valid_characters = r'[a-z0-9_-]'
    processed_topic_name = re.sub(f"[^{valid_characters}]", '', s)
    # 首字母大写
    processed_topic_name = processed_topic_name.capitalize()
    return processed_topic_name

def process_file_name(file_name):
    """
    处理文件名，去除非法字符
    :param file_name: 文件名
    """
    file_name = re.sub(r"[\\/:*?\"<>|\r\n]+", "_", file_name.strip())
    file_name = file_name.strip(".")
    return file_name
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
    pattern = "https?://.*?\.(?:jpg|jpeg|png|gif)"
    img_urls = re.findall(
        pattern,
        text)
    img_urls = [url for url in img_urls if is_valid_image_url(url)]
    return img_urls
""

def is_valid_image_url(url):
    """
    校验图片URL是否合法
    :param url: 图片URL
    :return: bool
    """
    try:
        # 发送HEAD请求验证URL
        response = requests.head(url, timeout=5)
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', '')
            if content_type.startswith('image'):
                return True
            
            if content_type.startswith('application/octet-stream'):
                return True       
    except Exception as e:
        logger.error(f"图片URL校验失败，URL: {url}, 异常信息: {e}")
        return False
    logger.info(f"图片URL不合法，URL: {url}")
    return False


