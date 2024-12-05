import os
import shutil

import pandas as pd
import openpyxl
import zipfile
import tiktoken
from fastapi.responses import HTMLResponse
from src.utils.logger import logger



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

    logger.info(f'文件夹 "{folder_path}" 已被压缩为 "{output_zip_file}"')
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
            logger.info(f'Markdown文件已生成：{markdown_file_path}')
    # 删除excel文件
    os.remove(excel_file_path)
    return zip_folder(output_folder)


def is_xlsx_file(file_path):
    # 获取文件扩展名
    _, ext = os.path.splitext(file_path)
    # 检查扩展名是否为Excel格式
    return ext.lower() == '.xlsx'

def generate_signature(secret, message):
    secret = secret.encode('utf-8')
    summary_info = ",".join([
        message.robot_id, message.robot_name, message.operator_openid,
        message.operator_name, message.time_stamp, message.msg_id, message.content])
    summary_info = summary_info.encode('utf-8')
    signature = hmac.new(secret, summary_info, hashlib.sha1)
    return base64.b64encode(signature.digest()).decode('utf-8')

#tiktoken

def openai_num_tokens_from_string(string):
    """Return the number of tokens."""
    encoding = tiktoken.get_encoding("cl100k_base")
    num_tokens = len(encoding.encode(string))
    return num_tokens

def openai_truncate_string(string, max_tokens):
    """Truncate the string to the maximum number of tokens."""
    encoding = tiktoken.get_encoding("cl100k_base")
    return encoding.decode(encoding.encode(string)[:max_tokens])



# def create_html_response(success: bool, message: str) -> HTMLResponse:
#     """
#     创建带有弹窗的 HTML 响应，支持多平台和移动端关闭窗口
#
#     :param success: 操作是否成功
#     :param message: 要显示的消息
#     :return: HTMLResponse 对象
#     """
#     # 根据 success 参数设置表情和颜色
#     icon = "&#128578;"  # 默认笑脸（操作成功）
#     color = "#4285f4"
#     if not success:
#         icon = "&#128577;"  # 操作失败时使用悲伤表情
#
#     html_content = f"""
#     <!DOCTYPE html>
#     <html lang="zh-CN">
#     <head>
#         <meta charset="UTF-8">
#         <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
#         <title>反馈结果</title>
#         <style>
#             html, body {{
#                 height: 100%;
#                 margin: 0;
#                 padding: 0;
#             }}
#             body {{
#                 display: flex;
#                 justify-content: center;
#                 align-items: center;
#                 font-family: Arial, sans-serif;
#                 background-color: rgba(0,0,0,0.1);
#                 overscroll-behavior: contain;
#             }}
#             .modal {{
#                 background-color: white;
#                 border-radius: 12px;
#                 box-shadow: 0 8px 16px rgba(0,0,0,0.15);
#                 padding: 25px;
#                 text-align: center;
#                 max-width: 320px;
#                 width: 90%;
#                 position: relative;
#                 overflow: hidden;
#             }}
#             .modal-title {{
#                 font-size: 24px;
#                 color: {color};
#                 margin-bottom: 15px;
#             }}
#             .modal-message {{
#                 font-size: 18px;
#                 color: #666;
#                 margin-bottom: 20px;
#                 font-weight: bold;
#                 line-height: 1.4;
#             }}
#             .modal-icon {{
#                 font-size: 60px;
#                 margin-bottom: 20px;
#             }}
#             .modal-close {{
#                 background-color: {color};
#                 color: white;
#                 border: none;
#                 padding: 12px 25px;
#                 border-radius: 8px;
#                 cursor: pointer;
#                 font-size: 16px;
#                 transition: all 0.3s ease;
#                 outline: none;
#             }}
#             .modal-close:hover {{
#                 opacity: 0.9;
#                 transform: scale(1.05);
#             }}
#             .modal-close:active {{
#                 opacity: 0.8;
#                 transform: scale(0.95);
#             }}
#         </style>
#     </head>
#     <body>
#         <div class="modal">
#             <div class="modal-icon">
#                 {icon} <!-- 根据 success 显示相应表情 -->
#             </div>
#             <div class="modal-message">{message}</div>
#             <button class="modal-close" id="closeBtn">关闭</button>
#         </div>
#         <script>
#             function isDesktopBrowser() {{
#                 // 检测是否是桌面浏览器
#                 return !(
#                     /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)
#                 );
#             }}
#
#             function closeWindow() {{
#                 try {{
#                     // 桌面浏览器优先直接关闭
#                     if (isDesktopBrowser()) {{
#                         if (window.opener) {{
#                             // 通过 window.open() 打开的窗口直接关闭
#                             window.close();
#                         }} else {{
#                             // 如果不是通过 window.open() 打开，尝试关闭当前窗口
#                             window.open('', '_self').close();
#                         }}
#                     }} else {{
#                         // 移动设备回退或导航到空白页
#                         if (window.history.length > 1) {{
#                             window.history.back();
#                         }} else {{
#                             window.location.href = 'about:blank';
#                         }}
#                     }}
#                 }} catch (error) {{
#                     console.error('关闭窗口时发生错误:', error);
#                 }}
#             }}
#
#             // 页面加载后立即尝试关闭
#             window.onload = function() {{
#                 setTimeout(closeWindow, 5000);
#             }};
#
#             // 为关闭按钮添加事件
#             document.addEventListener('DOMContentLoaded', function() {{
#                 const closeBtn = document.getElementById('closeBtn');
#                 if (closeBtn) {{
#                     closeBtn.addEventListener('click', closeWindow);
#                 }}
#             }});
#         </script>
#     </body>
#     </html>
#     """
#     return HTMLResponse(content=html_content)

def create_html_response(success: bool, message: str) -> HTMLResponse:
    """
    创建带有弹窗的 HTML 响应，支持多平台和移动端关闭窗口

    :param success: 操作是否成功
    :param message: 要显示的消息
    :return: HTMLResponse 对象
    """
    # 根据 success 参数设置表情和颜色
    icon = "&#128578;"  # 默认笑脸（操作成功）
    color = "#4285f4"
    if not success:
        icon = "&#128577;"  # 操作失败时使用悲伤表情

    html_content = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>反馈结果</title>
        <style>
            html, body {{
                height: 100%;
                margin: 0;
                padding: 0;
            }}
            body {{
                display: flex;
                justify-content: center;
                align-items: center;
                font-family: Arial, sans-serif;
                background-color: rgba(0,0,0,0.1);
                overscroll-behavior: contain;
            }}
            .modal {{
                background-color: white;
                border-radius: 12px;
                box-shadow: 0 8px 16px rgba(0,0,0,0.15);
                padding: 25px;
                text-align: center;
                max-width: 320px;
                width: 90%;
                position: relative;
                overflow: hidden;
            }}
            .modal-title {{
                font-size: 24px;
                color: {color};
                margin-bottom: 15px;
            }}
            .modal-message {{
                font-size: 18px;
                color: #666;
                margin-bottom: 20px;
                font-weight: bold;
                line-height: 1.4;
            }}
            .modal-icon {{
                font-size: 60px;
                margin-bottom: 20px;
            }}
            .modal-close {{
                background-color: {color};
                color: white;
                border: none;
                padding: 12px 25px;
                border-radius: 8px;
                cursor: pointer;
                font-size: 16px;
                transition: all 0.3s ease;
                outline: none;
            }}
            .modal-close:hover {{
                opacity: 0.9;
                transform: scale(1.05);
            }}
            .modal-close:active {{
                opacity: 0.8;
                transform: scale(0.95);
            }}
        </style>
    </head>
    <body>
        <div class="modal">
            <div class="modal-icon">
                {icon} <!-- 根据 success 显示相应表情 -->
            </div>
            <div class="modal-message">{message}</div>
            <button class="modal-close" id="closeBtn">关闭</button>
        </div>
        <script>
            function isDesktopBrowser() {{
                // 检测是否是桌面浏览器
                return !(
                    /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)
                );
            }}

            function closeWindow() {{
                try {{
                    // 桌面浏览器优先直接关闭
                    if (isDesktopBrowser()) {{
                        if (window.opener) {{
                            // 通过 window.open() 打开的窗口直接关闭
                            window.close();
                        }} else {{
                            // 如果不是通过 window.open() 打开，尝试关闭当前窗口
                            window.open('', '_self').close();
                        }}
                    }} else {{
                        // 移动设备内WebView关闭方案
                        // 尝试多种通用的WebView关闭方法
                        try {{
                            // 方案1：Android WebView关闭
                            if (window.Android && window.Android.closeWebView) {{
                                window.Android.closeWebView();
                                return;
                            }}
                            // 方案2：iOS WebView关闭
                            if (window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.closeWebView) {{
                                window.webkit.messageHandlers.closeWebView.postMessage({{}});
                                return;
                            }}
                            // 方案3：React Native WebView
                            if (window.ReactNativeWebView && window.ReactNativeWebView.postMessage) {{
                                window.ReactNativeWebView.postMessage('closeWebView');
                                return;
                            }}
                            // 方案4：Cordova/PhoneGap 插件
                            if (window.cordova && window.cordova.InAppBrowser) {{
                                window.cordova.InAppBrowser.close();
                                return;
                            }}
                            // 方案5：通用回退
                            if (window.history.length > 1) {{
                                window.history.back();
                            }} else if (window.opener) {{
                                window.close();
                            }} else {{
                                // 最后的兜底方案
                                window.location.href = 'about:blank';
                            }}
                        }} catch (error) {{
                            console.error('关闭WebView时发生错误:', error);
                        }}
                    }}
                }} catch (error) {{
                    console.error('关闭窗口时发生错误:', error);
                }}
            }}

            // 页面加载后立即尝试关闭
            window.onload = function() {{
                setTimeout(closeWindow, 5000);
            }};

            // 为关闭按钮添加事件
            document.addEventListener('DOMContentLoaded', function() {{
                const closeBtn = document.getElementById('closeBtn');
                if (closeBtn) {{
                    closeBtn.addEventListener('click', closeWindow);
                }}
            }});
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)




