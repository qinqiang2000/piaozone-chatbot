from sqlalchemy import create_engine, Column, Integer, String, func, DateTime, Text, Index,Boolean
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from src.utils.logger import logger
import datetime

Base = declarative_base()

class FileAndUrlTable(Base):
    """用于存储文件id和 URL 的映射关系"""
    __tablename__ = 't_file_and_url_mapping'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    assistant_id = Column(String(255), nullable=False)
    file_id = Column(String(255), nullable=False)
    url = Column(String(255), nullable=False)

class QARecord(Base):
    """储存机器人问答信息"""
    __tablename__ = 't_qa_record'
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(255))
    msg_id = Column(String(255))
    topic_name = Column(String(500))
    question = Column(Text)
    answer = Column(Text)
    has_answer = Column(String(255))
    asker = Column(String(255))
    source = Column(Integer, default=0) #用于区分问答来源 yunzhijia-0 or zhichi-1 or other-2
    created_at = Column(DateTime, default=func.now())
    is_liked = Column(Boolean, default=False, comment='是否点赞')  # 新增点赞标志
    is_disliked = Column(Boolean, default=False, comment='是否点踩')  # 新增点踩标志
    __table_args__ = (Index('ix_source_created_at', 'source', 'created_at'),)


class SQLDatabase:
    """使用 SQLAlchemy 存储信息"""

    def __init__(self,user='root', password='12345', host='localhost', port=3306, db="kb",charset="utf8"):
        connection_url = f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{db}?charset={charset}"
        self.engine = create_engine(connection_url, pool_size=10, max_overflow=20, pool_timeout=30, pool_recycle=1800, echo=False)
        self.Session = sessionmaker(autocommit=False,autoflush=False, bind=self.engine)
        logger.debug("连接到 MySQL 服务器")

    def create_table(self, table_class):
        """创建表格"""
        try:
            Base.metadata.create_all(bind=self.engine, tables=[table_class.__table__])
            logger.debug(f"表格 {table_class.__tablename__} 创建成功或者已经存在")
        except Exception as e:
            logger.error(f"创建表格错误: {e}")
            raise e

    def insert_data(self, table_class, data):
        """插入数据"""
        try:
            with self.Session() as session:
                session.add(table_class(**data))
                session.commit()
            logger.debug(f"成功插入数据到 {table_class.__tablename__}")
        except Exception as e:
            logger.error(f"插入数据错误: {e}")
            raise e

    def batch_insert_data(self, table_class, data_list):
        """批量插入数据"""
        try:
            with self.Session() as session:
                session.bulk_insert_mappings(table_class, data_list)
                session.commit()
            logger.debug(f"成功批量插入 {len(data_list)} 条数据到 {table_class.__tablename__}")
        except Exception as e:
            logger.error(f"批量插入数据错误: {e}")
            raise e

    def update_data(self, table_class, filters, update_values):
        """根据简单条件更新数据"""
        try:
            with self.Session() as session:
                result = session.query(table_class).filter_by(**filters).update(update_values)
                session.commit()
            logger.debug(f"成功更新 {result} 行数据在 {table_class.__tablename__}")
        except Exception as e:
            logger.error(f"更新数据错误: {e}")
            raise e
    def complex_update_data(self, table_class, condition, update_values):
        """根据复杂条件更新数据"""
        try:
            with self.Session() as session:
                result = session.query(table_class).filter(condition).update(update_values)
                session.commit()
            logger.debug(f"成功更新 {result} 行数据在 {table_class.__tablename__}")
        except Exception as e:
            logger.error(f"更新数据错误: {e}")
            raise e

    def delete_data(self, table_class, filters):
        """根据简单条件删除数据"""
        try:
            with self.Session() as session:
                result = session.query(table_class).filter_by(**filters).delete()
                session.commit()
            logger.debug(f"成功删除 {result} 行数据从 {table_class.__tablename__}")
        except Exception as e:
            logger.error(f"删除数据错误: {e}")
            raise e

    def complex_delete_data(self, table_class, condition):
        """根据复杂条件删除数据"""
        try:
            with self.Session() as session:
                result = session.query(table_class).filter(condition).delete()
                session.commit()
            logger.debug(f"成功删除 {result} 行数据从 {table_class.__tablename__}")
        except Exception as e:
            logger.error(f"删除数据错误: {e}")
            raise e

    def query_data(self, table_class, filters=None):
        """基于简单条件查询数据"""
        try:
            with self.Session() as session:
                query = session.query(table_class)
                if filters:
                    query = query.filter_by(**filters)
                result = query.all()
            logger.debug(f"成功查询到 {len(result)} 行数据从 {table_class.__tablename__}")
            return result
        except Exception as e:
            logger.error(f"查询数据错误: {e}")
            raise e

    def complex_query_data(self, table_class, condition= None):
        """基于复杂条件查询数据"""
        try:
            with self.Session() as session:
                query = session.query(table_class)
                if condition is not None:
                    query = query.filter(condition)
                result = query.all()
            logger.debug(f"成功查询到 {len(result)} 行数据从 {table_class.__tablename__}")
            return result
        except Exception as e:
            logger.error(f"查询数据错误: {e}")
            raise e
