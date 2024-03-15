from typing import List, Dict, Tuple
from enum import Enum
import requests
import json

import pandas as pd

from src.utils.logger import logger
class AsstType(str, Enum):
    """助手类型"""
    OPENAI = "openai"
    AZURE = "azure"
class ConfigManager:
    """
    管理语雀、云之家群、GPT Assistant的关系配置
    """
    def __init__(self, yuque_base_url, yuque_namespace, yuque_auth_token, yuque_request_agent,
                 config_repo, config_slug, use_azure=False):
        self.config_url = f"{yuque_base_url}/repos/{yuque_namespace}/{config_repo}/docs/{config_slug}"
        self.config_headers = {
            "X-Auth-Token": yuque_auth_token,
            "User-Agent": yuque_request_agent
        }
        self.use_azure = use_azure
        self.config_data = []
        self.init_config()
        logger.info("配置信息初始化成功")
    def process_config(self,config_doc):
        sheet = json.loads(config_doc['body_sheet'])['data'][0]
        table = sheet['table']
        if len(table) >= 1:
            df = pd.DataFrame(table[1:], columns=table[0])
            logger.debug(f"配置数据：{df}")
        else:
            logger.error("配置文档不存在数据，请检查")
            return None
        del df['id']
        df.replace('', pd.NA, inplace=True)
        df.dropna(how='any', inplace=True)
        df.replace(pd.NA, '', inplace=True)
        df.drop_duplicates(inplace=True)
        df = df.astype(str).apply(lambda x: x.str.strip())
        df = df[df["valid"] == "Y"]
        if self.use_azure:
            df = df[df["assistant_type"] == AsstType.AZURE]
        else:
            df = df[df["assistant_type"] == AsstType.OPENAI]
        config_mid_data = df.to_dict(orient="records")
        config_data = dict()
        for ins in config_mid_data:
            if ins["repo"] not in config_data:
                config_data[ins["repo"]] = dict()
            if ins["toc_title"] not in config_data[ins["repo"]]:
                config_data[ins["repo"]][ins["toc_title"]] = dict()
            if "yzj_token" not in config_data[ins["repo"]][ins["toc_title"]]:
                config_data[ins["repo"]][ins["toc_title"]]["yzj_token"] = list()
            config_data[ins["repo"]][ins["toc_title"]]["gpt_assistant_id"] = ins["gpt_assistant_id"]
            config_data[ins["repo"]][ins["toc_title"]]["yzj_token"].append(ins["yzj_token"])
        return config_data
    def init_config(self):
        """初始化配置信息"""
        config_doc = self.get_condig_doc()
        self.config_data = self.process_config(config_doc)
    def update_config(self):
        """更新初始化配置"""
        try:
            new_config_doc = self.get_condig_doc()
            new_config_data = self.process_config(new_config_doc)
            old_asst_list = self.get_all_asst_id()
            old_repo_list = self.get_all_yq_repo()
            self.config_data = new_config_data
            new_asst_list = self.get_all_asst_id()
            new_repo_list = self.get_all_yq_repo()
            ## 获取新增知识库和新增gpt助手、删除知识库和删除的gpt助手
            add_repo = set(new_repo_list) - set(old_repo_list)
            del_repo = set(old_repo_list) - set(new_repo_list)
            add_asst = set(new_asst_list) - set(old_asst_list)
            del_asst = set(old_asst_list) - set(new_asst_list)
            logger.info(f"配置更新成功")
            return add_repo, del_repo, add_asst, del_asst
        except:
            logger.error("无法更新配置信息，请重新更新")
        return set(), set(), set(), set()
    def get_condig_doc(self) -> dict:
        """
        获取配置文档（语雀上的）
        :param repo: 知识库的唯一标识
        :param slug: url中的slug
        :return: 配置文档详情
        """
        logger.info(f"请求获取配置文档 {self.config_url}")
        try:
            response = requests.get(url=self.config_url, headers=self.config_headers)
            response.raise_for_status()
            return json.loads(response.text)["data"]
        except requests.exceptions.RequestException as e:
            logger.error(f"请求获取配置文档 {self.config_url} 失败: {str(e)}")
            raise Exception("请求获取配置文档失败")

    def get_assistant_id_by_yzj_token(self,yzj_token):
        """
        从云之家群token获取assistant_id
        """
        for repo, dirs in self.config_data.items():
            for info in dirs.values():
                if yzj_token in info['yzj_token']:
                    return info['gpt_assistant_id']
        return None

    def get_info_by_yzj_token(self,yzj_token):
        """
        从云之家群token获取语雀知识库id、分组title和assistant_id
        """
        repo, toc_title = self.get_yq_info_by_yzj_token(yzj_token)
        asst_id = self.get_assistant_id_by_yzj_token(yzj_token)

        return repo, toc_title, asst_id

    def get_yq_info_by_yzj_token(self,yzj_token):
        """
        从云之家群token获取语雀知识库id和分组id
        """
        for repo, dirs in self.config_data.items():
            for toc_title, info in dirs.items():
                if yzj_token in info['yzj_token']:
                    return repo, toc_title
        return None, None

    def get_yzj_token_and_asst_id_by_yq_info(self,repo_name, toc_title_name):
        """
        基于语雀知识库id和分组title获取云之家群token和assistant_id
        """
        for repo, dirs in self.config_data.items():
            if repo == repo_name:
                for toc_title, info in dirs.items():
                    if toc_title == toc_title_name:
                        return info['yzj_token'], info['gpt_assistant_id']
        return None, None

    # 获取所有的语雀知识库id和分组title
    def get_all_yq_info(self):
        """
        获取所有的语雀知识库id和分组title
        """
        yq_info = []
        for repo, dirs in self.config_data.items():
            for toc_title in dirs:
                yq_info.append((repo, toc_title))
        return yq_info

    def get_all_yq_repo(self):
        """
        获取所有的语雀知识库id
        """
        return list(self.config_data.keys())

    def get_yq_info_by_asst_id(self, asst_id):
        """
        基于助手id获取语雀信息
        """
        for repo, dirs in self.config_data.items():
            for toc_title, info in dirs.items():
                if asst_id == info['gpt_assistant_id']:
                    return repo, toc_title
        return None, None

    def get_all_asst_id(self):
        """
        获取所有的助手id
        """
        asst_ids = []
        for repo, dirs in self.config_data.items():
            for toc_title, info in dirs.items():
                asst_ids.append(info['gpt_assistant_id'])
        return asst_ids