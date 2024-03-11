from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from config.settings import *
from src.sync.sync_flow import SyncFlow

scheduler = AsyncIOScheduler()

def setup_scheduler():
    # 启动定时任务：同步语雀文档到gpt assistant
    # scheduler.add_job(yuque_utils.sync_yuque_docs_2_assistant, CronTrigger(hour=2))
    # scheduler.start()
    logging.info("定时任务暂不启动")

def shutdown_scheduler():
    scheduler.shutdown()
    logging.info("定时任务关闭")