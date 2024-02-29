"""
GPT Assistant writer模块，提供同步数据到GPT Assistant的功能
"""

import traceback

from src.utils.logger import logger

class OpenAIAsstWriter:
    def __init__(self, api_key: str = None, azure_endpoint: str = None, api_version: str = None,
                 base_url: str = None, use_azure: bool = False):
        if use_azure:
            from openai import AzureOpenAI
            self.client = AzureOpenAI(api_key=api_key, api_version=api_version, azure_endpoint=azure_endpoint)
        else:
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key, base_url=base_url)
    def __call__(self,docs_path: list, assistant_id: str) -> bool:
        # 清空原有数据
        if self.empty_files(assistant_id) < 0:
            logger.error(f"同步数据gpt assistant失败，无法清空原有数据：{assistant_id}")
            return False
        # 同步所有文件
        # for f in docs_path:
        #     self.create_file(f, assistant_id)

        assistant_files = []
        for f in docs_path:
            assistant_file = self.create_file(f, assistant_id)
            assistant_files.append(assistant_file)
        assistant = self.client.beta.assistants.update(
            assistant_id=assistant_id,
            file_ids=[file.id for file in assistant_files]
        )
        logger.debug(f"同步数据gpt assistant成功。 {assistant.id}")
        return True
    def empty_files(self, assistant_id: str) -> int:
        """
        清空assistant的文件
        :param assistant_id: assistant id
        :return: 清空的文件数量；-1 表示清空失败
        """
        try:
            assistant_files = self.client.beta.assistants.files.list(
                assistant_id=assistant_id,
                limit=100
            )

            deleted_id = []
            for file in assistant_files.data:
                self.client.beta.assistants.files.delete(assistant_id=assistant_id, file_id=file.id)
                self.client.files.delete(file.id)
                deleted_id.append(file.id)

            logger.info(f"已清空assistant【{assistant_id}】文件：{deleted_id}，共{len(deleted_id)}个")
            return len(deleted_id)
        except Exception as e:
            logger.error(f"清空assistant【{assistant_id}】文件失败：{e}")
            return -1

    def create_file(self, file_path: str, assistant_id: str):
        """上传新文件
        :param file_path: 文件路径
        :param assistant_id: assistant id
        """
        with open(file_path, "rb") as f:
            file = self.client.files.create(
                file=f,
                purpose='assistants'
            )
            logger.info(f"已上传文件：{file_path}，文件id：{file.id}")
            return file
            # # 加载到新文件到assistant
            # assistant_file = self.client.beta.assistants.files.create(
            #     assistant_id=assistant_id,
            #     file_id=file.id
            # )
            # logger.info(f"已上传文件：{file_path}，文件id：{assistant_file.id}")
            # return assistant_file