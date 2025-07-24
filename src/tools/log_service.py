
from elasticsearch import Elasticsearch
from src.utils.logger import logger

class LogService:
    """日志服务类，负责从ES获取和处理日志"""
    
    def __init__(self, host: str, port: int, username: str=None, password: str=None, index: str=None):
        """初始化ES连接"""
        self.es_client = None
        self._init_es_connection(username, password, host, port)
        self.index = index
    def _init_es_connection(self, username: str, password: str, host: str, port: int):
        """初始化Elasticsearch连接"""
        try:
            if username and password:
                self.es_client = Elasticsearch(
                    [f"{host}:{port}"],
                    basic_auth=(username, password)
                )
            else:
                self.es_client = Elasticsearch([f"{host}:{port}"])

            if not self.es_client.ping():
                raise ConnectionError("Cannot connect to Elasticsearch")
        except Exception as e:
            raise e
    
    def _mask_sensitive_data(self, text: str) -> str:
        """脱敏处理敏感信息"""
        if not text:
            return text
        
        # 脱敏规则
        masking_rules = [
            # 手机号脱敏 (保留前3位和后4位)
            (r'(\d{3})\d{4}(\d{4})', r'\1****\2'),
            # 身份证号脱敏 (保留前6位和后4位)
            (r'(\d{6})\d{8}(\d{4})', r'\1********\2'),
            # 银行卡号脱敏 (保留前4位和后4位)
            (r'(\d{4})\d{8,12}(\d{4})', r'\1********\2'),
            # 税号脱敏 (保留前4位和后4位)
            (r'(\d{4})\d{7,12}(\d{4})', r'\1*******\2'),
            # 邮箱脱敏
            (r'([a-zA-Z0-9._%+-]{1,3})[a-zA-Z0-9._%+-]*@', r'\1***@'),
        ]
        
        import re
        masked_text = text
        for pattern, replacement in masking_rules:
            masked_text = re.sub(pattern, replacement, masked_text)
        
        return masked_text
    def get_logs_from_es(self, trace_id: str) -> dict:
        """
        根据trace_id从ES获取日志
        
        Args:
            trace_id: 追踪ID关键词
            
        Returns:
            dict格式的结果：{"result": [...]} 或 {"error": "..."}
        """
        try:
            if not trace_id:
                return {"error": "trace_id is required"}
            
            # 使用multi_match在指定字段中进行短语搜索
            query = {
                "query": {
                    "multi_match": {
                        "type": "phrase",
                        "query": trace_id,
                        "lenient": True,
                        "fields": ["msg", "id"]  # 只在msg和id字段中搜索
                    }
                },
                # 只返回需要的字段
                "_source": ["@timestamp", "id", "msg", "level"],
                # 按时间倒序排列，获取最新的记录
                "sort": [{"@timestamp": {"order": "desc"}}],
                "size": 100  # 默认返回100条，如果超出则返回最新的100条
            }
            
            index_name = self.index
            
            response = self.es_client.search(
                index=index_name,
                body=query
            )
            
            logs = []
            for hit in response['hits']['hits']:
                log_entry = hit['_source']
                # 只保留需要的字段
                filtered_log = {
                    "@timestamp": log_entry.get("@timestamp"),
                    "id": log_entry.get("id"),
                    "level": log_entry.get("level"),
                    "msg": log_entry.get("msg")
                }
                logs.append(filtered_log)
            
            if not logs:
                return {"error": f"No logs found for trace_id: {trace_id}. Please check if the trace_id is correct."}
            
            # 反转列表，使其按时间从远到近排列
            logs.reverse()
            
            # 总是返回result结构
            return {
                "result": logs
                }
            
        except Exception as e:
            logger.error(f"Failed to get logs for trace_id {trace_id}: {e}")
            return {"error": f"Error retrieving logs: {str(e)}"}