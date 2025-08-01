from typing import Dict, List, Tuple, Any, Set, Optional
import pandas as pd
import requests
import json
from src.utils.logger import logger

class ConfigManager:
    """
    管理语雀、云之家群、GPT Assistant的关系配置
    """

    def __init__(self, yuque_config: Dict[str, str], config_info: Dict[str, str]):
        self.config_info_tuple = [(config_info["asst_info_repo"], config_info["asst_info_slug"]),
                                  (config_info["yzj_info_repo"], config_info["yzj_info_slug"]),
                                  (config_info["zhichi_info_repo"], config_info["zhichi_info_slug"])]
        self.asst_config_url = f"{yuque_config['yuque_base_url']}/repos/{yuque_config['yuque_namespace']}/{config_info['asst_info_repo']}/docs/{config_info['asst_info_slug']}"
        self.yzj_config_url = f"{yuque_config['yuque_base_url']}/repos/{yuque_config['yuque_namespace']}/{config_info['yzj_info_repo']}/docs/{config_info['yzj_info_slug']}"
        self.zhichi_config_url = f"{yuque_config['yuque_base_url']}/repos/{yuque_config['yuque_namespace']}/{config_info['zhichi_info_repo']}/docs/{config_info['zhichi_info_slug']}"
        self.config_headers = {
            "X-Auth-Token": yuque_config['yuque_auth_token'],
            "User-Agent": yuque_config['yuque_request_agent']
        }
        self.index_data = self.set_config()
        logger.info("配置信息初始化成功")

    def _process_sheet_data(self, sheet_data: List[List[str]], key_columns: Optional[List[str]] = None) -> pd.DataFrame:
        """
        处理语雀表格数据, 转换为 pandas DataFrame
        :param sheet_data: 语雀表格数据
        :param key_columns: 关键列，如果关键列没有值需要过滤
        :return: pandas DataFrame
        """
        if len(sheet_data) >= 1:
            df = pd.DataFrame(sheet_data[1:], columns=sheet_data[0])
        else:
            logger.warning("配置文档不存在数据，请检查")
            return pd.DataFrame()
        # 删除无用列
        df = df.drop(['id', 'remark'], axis=1, errors='ignore')
        if key_columns:
            df.drop_duplicates(subset=key_columns,inplace=True)
        else:
            df.drop_duplicates(inplace=True)
        df = df.astype(str).apply(lambda x: x.str.strip())
        df = df[df["valid"] == "Y"]
        return df
    def _build_asst_index_data(self, config_df: pd.DataFrame) -> None:
        """
        根据配置数据构建索引数据, 严格检查空值
        :param config_df: 配置数据 DataFrame
        """
        config_df.drop_duplicates(subset=["assistant_id", "repo", "toc_title"], inplace=True)
        index_data = {}
        
        for _, row in config_df.iterrows():
            repo = row["repo"]
            toc_title = row["toc_title"]
            assistant_id = row["assistant_id"]
            assistant_type = row["assistant_type"]
            llm_type = row["llm_type"]
            
            if assistant_id not in index_data:
                index_data[assistant_id] = {
                    "assistant_type": assistant_type,
                    "llm_type": llm_type
                }
            
            # 严格检查repo是否为有效值（非空且不是纯空白）
            if pd.notna(repo) and str(repo).strip():
                if "yq_info" not in index_data[assistant_id]:
                    index_data[assistant_id]["yq_info"] = []
                index_data[assistant_id]["yq_info"].append((repo, toc_title))
        
        return index_data
    def _build_yzj_index_data(self, config_df: pd.DataFrame) -> None:
        """
        根据配置数据构建索引数据, 提高查询效率
        :param config_df: 配置数据 DataFrame
        """
        config_df.drop_duplicates(subset=["yzj_token"], inplace=True) # 多个yzj_token可以对应一个assistant,yzj_token则是唯一的
        index_data = {}
        for _, row in config_df.iterrows():
            yzj_token = row["yzj_token"]
            assistant_id = row["assistant_id"]
            # 是否自动录入FAQ
            is_auto_entry = True if row["is_auto_entry"] == "Y" else False
            # 是否接收系统信息配置
            is_receive_system_msg = True if row.get("is_receive_system_msg", "N") == "Y" else False
            index_data[yzj_token] = {
                "assistant_id": assistant_id,
                "is_auto_entry": is_auto_entry,
                "is_receive_system_msg": is_receive_system_msg
            }
        return index_data
    def _build_zhichi_index_data(self, config_df: pd.DataFrame) -> None:
        """
        根据配置数据构建索引数据, 提高查询效率
        :param config_df: 配置数据 DataFrame
        """
        index_data = {}
        for _, row in config_df.iterrows():
            assistant_id = row["assistant_id"]
            is_auto_entry = True if row["is_auto_entry"] == "Y" else False
            index_data[assistant_id] = {
                "is_auto_entry": is_auto_entry
            }
        return index_data

    def set_config(self) -> None:
        """初始化配置信息"""
        # 1. 获取助手配置信息
        asst_config_doc = self.get_config_doc(self.asst_config_url)
        asst_sheet_data = json.loads(asst_config_doc['body_sheet'])['data'][0]['table']
        asst_config_df = self._process_sheet_data(asst_sheet_data, ['repo','toc_title','assistant_id', 'assistant_type','llm_type','valid'])
        asst_config_dict = self._build_asst_index_data(asst_config_df)
        # 2. 获取云之家配置信息
        yzj_config_doc = self.get_config_doc(self.yzj_config_url)
        yzj_sheet_data = json.loads(yzj_config_doc['body_sheet'])['data'][0]['table']
        yzj_config_df = self._process_sheet_data(yzj_sheet_data, ['assistant_id', 'yzj_token', 'valid','is_auto_entry'])
        yzj_config_dict = self._build_yzj_index_data(yzj_config_df)
        for _, asst_info in yzj_config_dict.items():
            if asst_info["assistant_id"] not in asst_config_dict:
                raise ValueError(f"云之家配置信息中存在不合法的assistant_id: '{asst_info['assistant_id']}'，请检查！")
        # 3. 获取智齿配置信息
        zhichi_config_doc = self.get_config_doc(self.zhichi_config_url)
        zhichi_sheet_data = json.loads(zhichi_config_doc['body_sheet'])['data'][0]['table']
        zhichi_config_df = self._process_sheet_data(zhichi_sheet_data,['assistant_id', 'valid','is_auto_entry'])
        zhichi_config_dict = self._build_zhichi_index_data(zhichi_config_df)
        for asst_id in zhichi_config_dict:
            if asst_id not in asst_config_dict:
                raise ValueError(f"智齿配置信息中存在不合法的assistant_id: '{asst_id}'，请检查！")

        return {
            "asst_config": asst_config_dict,
            "yzj_config": yzj_config_dict,
            "zhichi_config": zhichi_config_dict
        }

    def update_config(self) -> Tuple[Set[str], Set[str], Set[str], Set[str]]:
        """更新配置信息"""
        new_index_data = self.set_config()

        old_asst_list = set(self.get_all_asst_id())
        old_repo_list = set(self.get_all_yq_repo())

        self.index_data = new_index_data
        new_asst_list = set(self.get_all_asst_id())
        new_repo_list = set(self.get_all_yq_repo())

        add_repo = new_repo_list - old_repo_list
        del_repo = old_repo_list - new_repo_list
        add_asst = new_asst_list - old_asst_list
        del_asst = old_asst_list - new_asst_list

        return add_repo, del_repo, add_asst, del_asst

    def get_config_doc(self, config_url: str) -> Dict[str, Any]:
        """
        获取配置文档（语雀上的）
        :return: 配置文档详情
        """
        try:
            response = requests.get(url=config_url, headers=self.config_headers)
            response.raise_for_status()
            return json.loads(response.text)["data"]
        except requests.exceptions.RequestException as e:
            logger.error(f"请求获取配置文档 {config_url} 失败: {str(e)}")
            raise Exception("请求获取配置文档失败")

    def get_assistant_id_by_yzj_token(self, yzj_token: str) -> Optional[str]:
        """
        从云之家群token获取assistant_id
        :param yzj_token: 云之家群 token
        :return: assistant_id
        """
        return self.index_data.get("yzj_config", {}).get(yzj_token, {}).get("assistant_id")
    def get_auto_entry_info_by_yzj_token(self, yzj_token: str) -> bool:
        """
        从云之家群token获取是否自动录入问答
        :param yzj_token: 云之家群 token
        :return: is_auto_entry
        """
        return self.index_data.get("yzj_config", {}).get(yzj_token, {}).get("is_auto_entry", False)

    def get_receive_system_msg_info_by_yzj_token(self, yzj_token: str) -> bool:
        """
        从云之家群token获取是否接收系统信息
        :param yzj_token: 云之家群 token
        :return: is_receive_system_msg
        """
        return self.index_data.get("yzj_config", {}).get(yzj_token, {}).get("is_receive_system_msg", False)


    def get_yq_info_by_yzj_token(self, yzj_token: str) -> List[Tuple[str, str]]:
        """
        从云之家群token获取语雀知识库id和分组id
        :param yzj_token: 云之家群 token
        :return: [(语雀知识库id, 分组title)]
        """
        asst_id = self.get_assistant_id_by_yzj_token(yzj_token)
        return self.get_yq_info_by_asst_id(asst_id)


    def get_all_yq_repo(self) -> List[str]:
        """
        获取所有的语雀知识库id
        :return: 语雀知识库id列表
        """
        repo_list = set()
        for _, asst_info in self.index_data.get("asst_config", {}).items():
            for yq_info in asst_info.get('yq_info', []):
                repo_list.add(yq_info[0])
        return list(repo_list)

    def get_yq_info_by_asst_id(self, asst_id: str) -> List[Tuple[str, str]]:
        """
        基于助手id获取语雀信息
        :param asst_id: 助手id
        :return: [(语雀知识库id, 分组title)]
        """
        asst_info = self.index_data.get("asst_config", {}).get(asst_id, {})
        return asst_info.get("yq_info", [])


    def get_asst_info_by_asst_id(self, asst_id: str) -> Tuple[int, str]:
        """
        基于助手id获取助手信息
        :param asst_id: 助手id
        :return: 助手类型, LLM类型
        """
        asst_info = self.index_data.get("asst_config", {}).get(asst_id, {})
        return asst_info.get("assistant_type"), asst_info.get("llm_type")

    def get_yzj_token_by_asst_id(self, asst_id: str) -> str:
        """
        基于助手id获取云之家群token
        :param asst_id: 助手id
        :return: 云之家群token
        """
        yzj_tokens = []
        for yzj_token, yzj_info in self.index_data.get("yzj_config", {}).items():
            if asst_id == yzj_info["assistant_id"]:
                yzj_tokens.append(yzj_token)
        return yzj_tokens

    def get_all_asst_id(self) -> List[str]:
        """
        获取所有的助手id
        :return: 助手id列表
        """
        return list(self.index_data.get("asst_config",{}))