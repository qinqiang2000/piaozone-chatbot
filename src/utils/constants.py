from enum import Enum

class QSource(str, Enum):
    """问题来源"""
    YZJ = "yzj"
    ZHICHI = "zhichi"
    OTHER = "other"