from typing import Dict, List, Tuple, Any, Set, Optional
import pandas as pd
import requests
import json
from src.utils.logger import logger

class ConfigManager:
    """
    管理语雀、云之家群、GPT Assistant的关系配置
    """

    def __init__(self, yuque_config: Dict[str, str], config_repo: str, config_slug: str):
        self.config_url = f"{yuque_config['yuque_base_url']}/repos/{yuque_config['yuque_namespace']}/{config_repo}/docs/{config_slug}"
        self.config_headers = {
            "X-Auth-Token": yuque_config['yuque_auth_token'],
            "User-Agent": yuque_config['yuque_request_agent']
        }
        self.index_data: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self.init_config()
        logger.info("配置信息初始化成功")

    def _process_sheet_data(self, sheet_data: List[List[str]]) -> pd.DataFrame:
        """
        处理语雀表格数据, 转换为 pandas DataFrame
        :param sheet_data: 语雀表格数据
        :return: pandas DataFrame
        """
        if len(sheet_data) >= 1:
            df = pd.DataFrame(sheet_data[1:], columns=sheet_data[0])
        else:
            logger.error("配置文档不存在数据，请检查")
            return pd.DataFrame()
        del df['id']
        del df['remark']
        df.replace('', pd.NA, inplace=True)
        df.dropna(how='any', inplace=True)
        df.replace(pd.NA, '', inplace=True)
        df.drop_duplicates(inplace=True)
        df = df.astype(str).apply(lambda x: x.str.strip())
        df = df[df["valid"] == "Y"]
        df["assistant_type"] = df["assistant_type"].apply(float).apply(int)
        df.drop_duplicates(subset=["yzj_token"], inplace=True)  # 多个yzj_token可以对应一个assistant,yzj_token则是唯一的
        return df

    def _build_index_data(self, config_df: pd.DataFrame) -> None:
        """
        根据配置数据构建索引数据, 提高查询效率
        {repo:toc_title:assistant_id:{'assistant_type':'','llm_type':'','yzj_token':[]}}
        :param config_df: 配置数据 DataFrame
        """
        self.index_data = {}
        for _, row in config_df.iterrows():
            repo = row["repo"]
            toc_title = row["toc_title"]
            assistant_id = row["assistant_id"]
            assistant_type = row["assistant_type"]
            llm_type = row["llm_type"]
            yzj_token = row["yzj_token"]

            if repo not in self.index_data:
                self.index_data[repo] = {}
            if toc_title not in self.index_data[repo]:
                self.index_data[repo][toc_title] = {}
            if assistant_id not in self.index_data[repo][toc_title]:
                self.index_data[repo][toc_title][assistant_id] = {
                    "assistant_type": assistant_type,
                    "llm_type": llm_type,
                    "yzj_token": []
                }

            self.index_data[repo][toc_title][assistant_id]["yzj_token"].append(yzj_token)


    def init_config(self) -> None:
        """初始化配置信息"""
        config_doc = self.get_config_doc()
        sheet_data = json.loads(config_doc['body_sheet'])['data'][0]['table']
        config_df = self._process_sheet_data(sheet_data)
        self._build_index_data(config_df)

    def update_config(self) -> Tuple[Set[str], Set[str], Set[str], Set[str]]:
        """更新配置信息"""
        try:
            new_config_doc = self.get_config_doc()
            sheet_data = json.loads(new_config_doc['body_sheet'])['data'][0]['table']
            new_config_df = self._process_sheet_data(sheet_data)

            old_asst_list = set(self.get_all_asst_id())
            old_repo_list = set(self.index_data.keys())

            self._build_index_data(new_config_df)
            new_asst_list = set(self.get_all_asst_id())
            new_repo_list = set(self.index_data.keys())

            add_repo = new_repo_list - old_repo_list
            del_repo = old_repo_list - new_repo_list
            add_asst = new_asst_list - old_asst_list
            del_asst = old_asst_list - new_asst_list

            logger.info("配置更新成功")
            return add_repo, del_repo, add_asst, del_asst
        except Exception as e:
            logger.error(f"无法更新配置信息: {str(e)}")
            return set(), set(), set(), set()

    def get_config_doc(self) -> Dict[str, Any]:
        """
        获取配置文档（语雀上的）
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

    def get_assistant_id_by_yzj_token(self, yzj_token: str) -> Optional[str]:
        """
        从云之家群token获取assistant_id
        :param yzj_token: 云之家群 token
        :return: assistant_id
        """
        for repo, dirs in self.index_data.items():
            for info in dirs.values():
                for asst_id, asst_info in info.items():
                    if yzj_token in asst_info['yzj_token']:
                        return asst_id
        return None

    def get_info_by_yzj_token(self, yzj_token: str) -> Tuple[str, str, str]:
        """
        从云之家群token获取语雀知识库id、分组title和assistant_id
        :param yzj_token: 云之家群 token
        :return: 语雀知识库id, 分组title, assistant_id
        """
        repo, toc_title = self.get_yq_info_by_yzj_token(yzj_token)
        asst_id = self.get_assistant_id_by_yzj_token(yzj_token)
        return repo, toc_title, asst_id

    def get_yq_info_by_yzj_token(self, yzj_token: str) -> Tuple[str, str]:
        """
        从云之家群token获取语雀知识库id和分组id
        :param yzj_token: 云之家群 token
        :return: 语雀知识库id, 分组title
        """
        for repo, dirs in self.index_data.items():
            for toc_title, info in dirs.items():
                for asst_info in info.values():
                    if yzj_token in asst_info['yzj_token']:
                        return repo, toc_title
        return None, None
    def get_yzj_token_and_asst_id_by_yq_info(self, repo_name: str, toc_title_name: str) -> List[Tuple[str, str]]:
        """
        基于语雀知识库id和分组title获取云之家群token和assistant_id
        :param repo_name: 语雀知识库id
        :param toc_title_name: 分组title
        :return: 列表 ([云之家群token], assistant_id)
        """
        res = []
        if repo_name in self.index_data:
            if toc_title_name in self.index_data[repo_name]:
                info = self.index_data[repo_name][toc_title_name]
                for asst_id, asst_info in info.items():
                    res.append((asst_info['yzj_token'], asst_id))
        return res

    def get_all_yq_info(self) -> List[Tuple[str, str]]:
        """
        获取所有的语雀知识库id和分组title
        :return: 列表のof (语雀知识库id, 分组title)
        """
        yq_info = []
        for repo, dirs in self.index_data.items():
            for toc_title in dirs:
                yq_info.append((repo, toc_title))
        return yq_info

    def get_all_yq_repo(self) -> List[str]:
        """
        获取所有的语雀知识库id
        :return: 语雀知识库id列表
        """
        return list(self.index_data.keys())

    def get_yq_info_by_asst_id(self, asst_id: str) -> Tuple[str, str]:
        """
        基于助手id获取语雀信息
        :param asst_id: 助手id
        :return: 语雀知识库id, 分组title
        """
        for repo, dirs in self.index_data.items():
            for toc_title, info in dirs.items():
                if asst_id in info:
                    return repo, toc_title
        return None, None

    def get_all_asst_info(self) -> List[Tuple[str, int, str]]:
        """
        获取所有的助手信息
        :return: 列表 (助手id, 助手类型, LLM类型)
        """
        asst_info = []
        for repo, dirs in self.index_data.items():
            for toc_title, info in dirs.items():
                for asst_id, asst_ins in info.items():
                    asst_info.append((asst_id, asst_ins["assistant_type"], asst_ins["llm_type"]))
        return asst_info

    def get_asst_info_by_asst_id(self, asst_id: str) -> Tuple[int, str]:
        """
        基于助手id获取助手信息
        :param asst_id: 助手id
        :return: 助手类型, LLM类型
        """
        for repo, dirs in self.index_data.items():
            for toc_title, info in dirs.items():
                if asst_id in info:
                    asst_info = info[asst_id]
                    return asst_info["assistant_type"], asst_info["llm_type"]
        return None,None

    def get_yzj_token_by_asst_id(self, asst_id: str) -> str:
        """
        基于助手id获取云之家群token
        :param asst_id: 助手id
        :return: 云之家群token
        """
        for repo, dirs in self.index_data.items():
            for toc_title, info in dirs.items():
                if asst_id in info:
                    asst_info = info[asst_id]
                    return asst_info["yzj_token"]
        return None

    def get_all_asst_id(self) -> List[str]:
        """
        获取所有的助手id
        :return: 助手id列表
        """
        asst_ids = []
        for repo, dirs in self.index_data.items():
            for toc_title, info in dirs.items():
                asst_ids.extend(list(info.keys()))
        asst_ids =list(set(asst_ids))
        return asst_ids