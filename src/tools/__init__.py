from enum import Enum
from typing import Dict, Any, Callable, Union, Optional
from dataclasses import dataclass
from abc import ABC, abstractmethod
from src.tools.log_service import LogService
from src.utils.logger import logger
import os
# class ToolType(str, Enum):
#     """工具类型"""
#     RAG = "rag"

@dataclass
class ToolConfig:
    """工具配置类"""
    tool_name: str
    tool_type: str  # "function" 或 "class_method"
    class_name: Optional[str] = None
    method_name: Optional[str] = None
    init_params: Optional[Dict[str, Any]] = None

class ToolManager:
    """工具管理器，支持函数和类方法的统一管理"""
    
    def __init__(self, tools_config: list, assistant_config: dict, available_tools: dict):
        """
        初始化工具管理器
        
        Args:
            tools_config: 工具配置列表
            assistant_config: 助手配置，包含tool_settings
            available_tools: 可用工具字典，包含函数和类定义
        """
        self.tools_config = tools_config
        self.assistant_config = assistant_config
        self.available_tools = available_tools
        self.tools = {}
        self.tool_instances = {}  # 存储已初始化的类实例
        
        self._initialize_tools()
        logger.info(f"ToolManager initialized successfully")
        logger.info(f"tools: {self.tools}")
        logger.info(f"tool_instances: {self.tool_instances}")
    
    def _initialize_tools(self):
        """初始化所有工具"""
        for tool in self.tools_config:
            if tool["type"] == "function":
                tool_name = tool["function"]["name"]
                try:
                    if tool_name in self.available_tools:
                        tool_def = self.available_tools[tool_name]
                        
                        # 判断是否为类方法
                        if self._is_class_method(tool_def):
                            self.tools[tool_name] = self._initialize_class_method(tool_name, tool_def)
                        else:
                            # 普通函数直接使用
                            self.tools[tool_name] = tool_def
                    else:
                        logger.warning(f"Tool {tool_name} not found in available_tools")
                        
                except Exception as e:
                    logger.error(f"Failed to initialize tool {tool_name}: {e}")
    
    def _is_class_method(self, tool_def: Any) -> bool:
        """判断工具定义是否为类方法"""
        # 检查是否为类或包装器
        if hasattr(tool_def, '__dict__') and 'class_name' in tool_def.__dict__:
            return True
        if hasattr(tool_def, '_is_class_method'):
            return tool_def._is_class_method
        # 检查是否为类
        if isinstance(tool_def, type):
            return True
        return False
    
    def _initialize_class_method(self, tool_name: str, tool_def: Any) -> Callable:
        """初始化类方法工具"""
        try:
            # 获取工具配置
            tool_settings = self.assistant_config.get("tool_settings", {}).get(tool_name, {})
            
            # 如果tool_def是类，直接实例化
            if isinstance(tool_def, type):
                instance = tool_def(**tool_settings)
                self.tool_instances[tool_name] = instance
                # 返回实例的主要方法（假设有默认方法）
                if hasattr(instance, 'execute'):
                    return instance.execute
                elif hasattr(instance, '__call__'):
                    return instance
                else:
                    # 返回第一个非私有方法
                    for attr_name in dir(instance):
                        if not attr_name.startswith('_'):
                            attr = getattr(instance, attr_name)
                            if callable(attr):
                                return attr
            
            # 如果tool_def是包装器，从中提取类和方法信息
            elif hasattr(tool_def, 'class_name') and hasattr(tool_def, 'method_name'):
                class_name = tool_def.class_name
                method_name = tool_def.method_name
                
                # 从available_tools中获取类定义
                if class_name in self.available_tools:
                    cls = self.available_tools[class_name]
                    
                    # 检查是否已经实例化过
                    instance_key = f"{class_name}_{hash(frozenset(tool_settings.items()))}"
                    if instance_key not in self.tool_instances:
                        self.tool_instances[instance_key] = cls(**tool_settings)
                    
                    instance = self.tool_instances[instance_key]
                    return getattr(instance, method_name)
            
            # 如果tool_def已经是绑定方法，检查是否需要重新实例化
            elif hasattr(tool_def, '__self__'):
                # 获取类和方法名
                cls = tool_def.__self__.__class__
                method_name = tool_def.__name__
                
                # 使用新配置重新实例化
                new_instance = cls(**tool_settings)
                self.tool_instances[tool_name] = new_instance
                return getattr(new_instance, method_name)
            
            logger.error(f"Unable to initialize class method for tool: {tool_name}")
            return None
            
        except Exception as e:
            logger.error(f"Error initializing class method {tool_name}: {e}")
            return None
    
    def get_tool(self, tool_name: str) -> Optional[Callable]:
        """获取工具函数"""
        return self.tools.get(tool_name)
    
    def get_tool_instance(self, tool_name: str) -> Optional[Any]:
        """获取工具实例（如果是类方法）"""
        return self.tool_instances.get(tool_name)
    
    def reload_tool(self, tool_name: str):
        """重新加载指定工具"""
        for tool in self.tools_config:
            if tool["type"] == "function" and tool["function"]["name"] == tool_name:
                try:
                    if tool_name in self.available_tools:
                        tool_def = self.available_tools[tool_name]
                        
                        if self._is_class_method(tool_def):
                            self.tools[tool_name] = self._initialize_class_method(tool_name, tool_def)
                        else:
                            self.tools[tool_name] = tool_def
                        
                        logger.info(f"Tool {tool_name} reloaded successfully")
                    else:
                        logger.warning(f"Tool {tool_name} not found in available_tools")
                        
                except Exception as e:
                    logger.error(f"Failed to reload tool {tool_name}: {e}")
                break

# 工具包装器类，用于标记类方法
class ClassMethodTool:
    """类方法工具包装器"""
    
    def __init__(self, class_name: str, method_name: str, cls: type):
        self.class_name = class_name
        self.method_name = method_name
        self.cls = cls
        self._is_class_method = True
    
    def __call__(self, *args, **kwargs):
        """这个不应该被直接调用，只是为了标记"""
        raise NotImplementedError("This is a wrapper, should be initialized by ToolManager")

TOOLS = {
    "LogService": LogService,
    "get_logs_from_es": ClassMethodTool("LogService", "get_logs_from_es", LogService)
    }
