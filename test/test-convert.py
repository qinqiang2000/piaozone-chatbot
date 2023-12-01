import os
import os.path as osp
import mammoth
from pdf2docx.converter import Converter

# 定义一个忽略图片处理的函数
def ignore(image):
    return {"src": ""}  # 返回一个空的 src 属性，这样图片不会显示


# 遍历文件夹下的docx文件，转换为html文件
def convert_docx_to_html_folder(folder_path):
    for file in os.listdir(folder_path):
        if file.endswith(".docx") and not file.startswith("~$"):
            file_path = osp.join(folder_path, file)

            html_content = convert_docx_to_html(file_path)

            html_file_path = osp.join(folder_path, 'html', file.replace(".docx", ".html"))
            if not osp.exists(osp.dirname(html_file_path)):
                os.makedirs(osp.dirname(html_file_path))

            with open(html_file_path, "w", encoding="utf-8") as html_file:
                html_file.write(html_content)
            print(f"已经转换{file_path}为{html_file_path}")


def convert_docx_to_html(file_path):
    print(f"正在转换{file_path}")
    with open(file_path, "rb") as docx_file:
        result = mammoth.convert_to_html(docx_file, convert_image=mammoth.images.img_element(ignore))
        html_content = result.value  # 生成的 HTML 内容
        messages = result.messages  # 转换过程中的任何消息
        return html_content


def convert_pdf_to_docx(pdf_path):
    docx_filename = osp.join(osp.dirname(pdf_path), 'output.docx')

    cv = Converter(pdf_path)
    cv.convert(docx_filename=docx_filename, ignore_page_error=False, end=9)
    cv.close()

    return docx_filename


def convert_pdf_to_html(pdf_path):
    # 先转换为docx
    docx_path = convert_pdf_to_docx(pdf_path)

    # 再转换为html文本
    html_content = convert_docx_to_html(docx_path)

    # 保存为html文件
    html_path = osp.join(osp.dirname(pdf_path), 'output.html')
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)


if __name__ == '__main__':
    convert_pdf_to_html(r"/Users/qinqiang02/Desktop/乐企数字化电子发票（基础版）开票能力说明文档-V2.006.pdf")