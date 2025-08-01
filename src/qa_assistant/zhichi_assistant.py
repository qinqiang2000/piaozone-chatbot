import time
import traceback
import requests
import hashlib
import uuid
from datetime import datetime, timedelta

from src.qa_assistant.base_assistant import BaseAssistant, ASSTType
from src.utils.logger import logger
from src.utils.data_process import process_topic_name
from src.utils.database import SQLDatabase, QARecord

class Assistant(BaseAssistant):
    def __init__(self, assistant_id: str, assistant_config: dict, llm_configs: dict, topic: str, database: SQLDatabase):
        super().__init__(assistant_id, assistant_config, llm_configs)
        self.topic = process_topic_name(topic)
        self.asst_type = ASSTType.ZHICHI_ASSISTANT
        self.database = database
        self.session_map = {}  # 存储session_id和ai_agent_cid的映射关系
        
        # 获取LLM选项，默认使用zhichi
        llm_option = assistant_config.get('llm_option', 'zhichi')
        
        # 从llm_configs中获取智齿配置
        zhichi_config = llm_configs.get(llm_option, {})
        if not zhichi_config:
            raise ValueError(f"llm_configs中缺少{llm_option}配置")
        
        # 基础API配置
        self.appid = zhichi_config.get('appid')
        self.app_key = zhichi_config.get('app_key')
        self.base_url = zhichi_config.get('base_url', 'https://www.soboten.com')
        self.api_base_url = zhichi_config.get('api_base_url', 'https://api-c.soboten.com')
        
        # 验证必需配置
        if not self.appid or not self.app_key:
            raise ValueError("智齿配置中缺少appid或app_key")
        
        # 机器人配置 - 从assistant_config中获取
        self.robot_id = self.assistant_id
        
        # token管理
        self.token = None
        self.token_expire_time = None
        
        logger.info(f"[智齿助手]初始化完成: assistant_id={assistant_id}, robot_id={self.robot_id}")

    def _generate_sign(self, create_time: int) -> str:
        """生成签名 - 智齿固定使用MD5加密方式"""
        try:
            # 智齿签名规则：appid + create_time + app_key，然后MD5加密
            # 例如：appid="1", create_time="1569397773", app_key="2"
            # sign_str = "115693977732"
            # sign = MD5("115693977732") = "258eec3118705112b2c53dc8043d4d34"
            sign_str = f"{self.appid}{create_time}{self.app_key}"
            sign = hashlib.md5(sign_str.encode('utf-8')).hexdigest()
            logger.debug(f"[智齿助手]生成签名: sign_str={sign_str}, sign={sign}")
            return sign
        except Exception as e:
            logger.error(f"[智齿助手]生成签名失败: {e}")
            raise

    def _get_token(self) -> str:
        """获取token"""
        try:
            # 检查token是否过期（提前5分钟刷新）
            if self.token and self.token_expire_time and datetime.now() < self.token_expire_time:
                return self.token
            
            # 获取新token
            create_time = int(time.time())
            sign = self._generate_sign(create_time)
            
            url = f"{self.base_url}/api/get_token"
            params = {
                'appid': self.appid,
                'create_time': create_time,
                'sign': sign
            }
            
            logger.debug(f"[智齿助手]请求token: url={url}, params={params}")
            
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            logger.debug(f"[智齿助手]token响应: {result}")
            
            if result.get('ret_code') == '000000':
                self.token = result['item']['token']
                expires_in = int(result['item']['expires_in'])
                # 提前5分钟过期，避免token在请求过程中失效
                self.token_expire_time = datetime.now() + timedelta(seconds=expires_in - 300)
                logger.info(f"[智齿助手]获取token成功，过期时间: {self.token_expire_time}")
                return self.token
            else:
                logger.error(f"[智齿助手]获取token失败: {result}")
                return None
                
        except Exception as e:
            logger.error(f"[智齿助手]获取token异常: {e}\n{traceback.format_exc()}")
            return None

    def _init_conversation(self, session_id: str) -> dict:
        """初始化对话"""
        try:
            token = self._get_token()
            if not token:
                return None
            
            # 生成bizid（使用session_id的哈希值确保唯一性）
            bizid = hashlib.md5(f"{session_id}_{int(time.time())}".encode()).hexdigest()
            
            url = f"{self.api_base_url}/text/ai-agent-open/ask/ask_init"
            params = {
                'robotid': self.robot_id,
                'bizid': bizid
            }
            headers = {
                'token': token
            }
            
            logger.debug(f"[智齿助手]初始化对话请求: url={url}, params={params}")
            
            response = requests.get(url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            logger.debug(f"[智齿助手]初始化对话响应: {result}")
            
            if result.get('ret_code') == '000000':
                conv_info = result['data']
                self.session_map[session_id] = conv_info
                logger.info(f"[智齿助手]初始化对话成功: session_id={session_id}, ai_agent_cid={conv_info['ai_agent_cid']}")
                return conv_info
            else:
                logger.error(f"[智齿助手]初始化对话失败: {result}")
                return None
                
        except Exception as e:
            logger.error(f"[智齿助手]初始化对话异常: {e}\n{traceback.format_exc()}")
            return None

    def chat(self, session_id: str, content: str) -> tuple:
        """
        用户发送消息，调用智齿接口，返回回复
        :param session_id: 会话ID
        :param content: 用户输入的内容
        :return: (回复内容, 是否有答案)
        """
        try:
            # 1. 获取或初始化会话信息
            if session_id not in self.session_map:
                conv_info = self._init_conversation(session_id)
                if not conv_info:
                    return "初始化对话失败，请稍后重试", False
            else:
                conv_info = self.session_map[session_id]

            # 2. 获取token
            token = self._get_token()
            if not token:
                return "获取token失败，请稍后重试", False

            # 3. 发送问题
            url = f"{self.api_base_url}/text/ai-agent-open/ask/answer_no_stream"
            headers = {
                'token': token,
                'Content-Type': 'application/json'
            }
            
            payload = {
                "question": content,
                "show_question": content,
                "input_type_enum": "INPUT",
                "biz_id": conv_info['bizid'],
                "biz_type": conv_info['biz_type'],
                "biz_type_id": conv_info['biz_typeid'],
                "robotid": self.robot_id,
                "source_enum": "PC"
            }
            
            logger.debug(f"[智齿助手]提问请求: url={url}, payload={payload}")
            
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            logger.debug(f"[智齿助手]提问响应: {result}")
            
            if result.get('ret_code') == '000000':
                data = result['data'][0]  # 取第一个回答
                answer = data.get('answer', '')
                
                # 判断是否有有效答案
                no_answer_keywords = [
                    "非常抱歉，我暂时没有这个问题的答案",
                    "抱歉，我无法回答这个问题", 
                    "我不知道",
                    "无法提供相关信息",
                    "暂时没有这个问题的答案",
                    "不在我的专业范围内"
                ]
                has_answer = not any(keyword in answer for keyword in no_answer_keywords)
                
                logger.info(f"[智齿助手]问答成功: session_id={session_id}, has_answer={has_answer}, answer_length={len(answer)}")
                return answer, has_answer
            else:
                logger.error(f"[智齿助手]问答失败: {result}")
                
                # 检查是否是token失效，如果是则重新获取token并重试一次
                error_code = result.get('errcode') or result.get('ret_code')
                if error_code in ['401', '900002']:
                    logger.info("[智齿助手]token失效，重新获取并重试")
                    self.token = None
                    self.token_expire_time = None
                    # 递归重试一次（避免无限递归）
                    if hasattr(self, '_retry_count'):
                        return "系统繁忙，请稍后重试", False
                    self._retry_count = True
                    try:
                        return self.chat(session_id, content)
                    finally:
                        delattr(self, '_retry_count')
                
                return "系统繁忙，请稍后重试", False
                
        except Exception as e:
            logger.error(f"[智齿助手]问答异常: {e}\n{traceback.format_exc()}")
            return "系统异常，请稍后重试", False

    def end_session(self, session_id: str) -> bool:
        """结束会话"""
        try:
            if session_id not in self.session_map:
                logger.info(f"[智齿助手]会话不存在，无需结束: session_id={session_id}")
                return True
            
            conv_info = self.session_map[session_id]
            token = self._get_token()
            if not token:
                logger.error("[智齿助手]结束会话时获取token失败")
                # 即使token失败，也要清理本地缓存
                del self.session_map[session_id]
                return False
            
            url = f"{self.api_base_url}/text/ai-agent-open/ask/end_session"
            params = {
                'ai_agent_cid': conv_info['ai_agent_cid']
            }
            headers = {
                'token': token
            }
            
            logger.debug(f"[智齿助手]结束会话请求: url={url}, params={params}")
            
            response = requests.get(url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            logger.debug(f"[智齿助手]结束会话响应: {result}")
            
            # 无论API调用成功与否，都要清理本地缓存
            del self.session_map[session_id]
            
            if result.get('ret_code') == '000000':
                logger.info(f"[智齿助手]结束会话成功: session_id={session_id}")
                return True
            else:
                logger.error(f"[智齿助手]结束会话失败: {result}")
                return False
                
        except Exception as e:
            logger.error(f"[智齿助手]结束会话异常: {e}")
            # 异常情况下也要清理本地缓存
            if session_id in self.session_map:
                del self.session_map[session_id]
            return False

    def get_message_memory(self, session_id: str):
        """获取会话记忆（智齿API不支持获取历史消息）"""
        logger.warning("[智齿助手]不支持获取会话历史消息")
        return ["[智齿助手]不支持获取会话历史消息"]

    def save_qa_to_database(self, session_id: str = "", msg_id: str = "", topic_name: str = "", question: str = "",
                             answer: str = "", has_answer: bool = False, asker: str = "", source: int = 0) -> None:
        """保存问答记录到数据库"""
        try:
            has_answer_str = '是' if has_answer else '否'
            upload_data = {
                'session_id': session_id, 
                'msg_id': msg_id, 
                'topic_name': topic_name, 
                'question': question,
                'answer': answer, 
                'has_answer': has_answer_str, 
                'asker': asker, 
                'source': source
            }
            if has_answer_str == '否':
                upload_data['feedback'] = -1
            self.database.insert_data(QARecord, upload_data)
            logger.info(f"[智齿助手]问答数据录入成功: session_id={session_id}")
        except Exception as e:
            logger.error(f"[智齿助手]问答数据录入失败: {e}")

    def del_all_threads(self) -> None:
        """删除所有会话"""
        session_ids = list(self.session_map.keys())
        success_count = 0
        for session_id in session_ids:
            if self.end_session(session_id):
                success_count += 1
        logger.info(f"[智齿助手]删除所有会话完成，成功删除{success_count}/{len(session_ids)}个会话")

    def get_thread_id(self, session_id: str) -> str:
        """获取智齿的ai_agent_cid"""
        conv_info = self.session_map.get(session_id)
        return conv_info.get('ai_agent_cid') if conv_info else None

    def del_thread(self, session_id: str) -> None:
        """删除指定会话"""
        self.end_session(session_id)

    def create_assistant(self, name: str, instructions: str = None, model_name: str = None):
        """智齿助手不需要创建，返回当前robot_id"""
        logger.info(f"[智齿助手]使用已配置的robot_id: {self.robot_id}")
        return self.robot_id

    def del_assistant(self) -> None:
        """删除助手（清理所有会话）"""
        self.del_all_threads()
        logger.info(f"[智齿助手]助手清理完成")

    def check_asst_file(self) -> bool:
        return True