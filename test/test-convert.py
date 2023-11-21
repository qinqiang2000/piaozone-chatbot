import os

import mammoth


# 定义一个忽略图片处理的函数
def ignore(image):
    return {"src": ""}  # 返回一个空的 src 属性，这样图片不会显示


def convert_docx_to_html(file_path):
    print(f"正在转换{file_path}")
    with open(file_path, "rb") as docx_file:
        result = mammoth.convert_to_html(docx_file, convert_image=mammoth.images.img_element(ignore))
        html_content = result.value  # 生成的 HTML 内容
        messages = result.messages  # 转换过程中的任何消息
        return html_content


# 遍历文件夹下的docx文件，转换为html文件
def convert_docx_to_html_folder(folder_path):
    for file in os.listdir(folder_path):
        if file.endswith(".docx") and not file.startswith("~$"):
            file_path = os.path.join(folder_path, file)

            html_content = convert_docx_to_html(file_path)

            html_file_path = os.path.join(folder_path, 'html', file.replace(".docx", ".html"))
            if not os.path.exists(os.path.dirname(html_file_path)):
                os.makedirs(os.path.dirname(html_file_path))

            with open(html_file_path, "w", encoding="utf-8") as html_file:
                html_file.write(html_content)
            print(f"已经转换{file_path}为{html_file_path}")


if __name__ == '__main__':
    convert_docx_to_html_folder(r"/Users/qinqiang02/job/产品/数电票方案/微乐&乐企文档/乐企语料整理/output")
