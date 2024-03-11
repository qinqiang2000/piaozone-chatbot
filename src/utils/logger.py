import logging
import logging.handlers
import os
import time
import datetime
import shutil

from config.settings import LOG_DIR
LOG_CONF = {
    "name":__name__,
    "log_dir":LOG_DIR,
    "level": "info",
    # "formatter": "%(asctime)s.%(msecs)d [] [%(thread)d] %(levelname)s %(filename)s-%(funcName)s-%(message)s",
    "formatter": "[%(asctime)s %(filename)s:%(lineno)d] %(levelname)s: %(message)s",
    "when": "midnight",
    "backupCount": 30,
}

class LogFilter:
    @staticmethod
    def info_filter(record):
        if record.levelname == 'INFO':
            return True
        return False

    @staticmethod
    def error_filter(record):
        if record.levelname == 'ERROR':
            return True
        return False


class TimeLoggerRolloverHandler(logging.handlers.TimedRotatingFileHandler):
    def __init__(self, filename, when='h', interval=1, backupCount=0, encoding=None, delay=False, utc=False,
                 atTime=None):
        super(TimeLoggerRolloverHandler, self).__init__(filename, when, interval, backupCount, encoding, delay, utc)

    def doRollover(self):
        """
        TimedRotatingFileHandler对日志的切分是在满足设定的时间间隔后，执行doRollover方法，
        将my.log重命名为带有当前时间后缀(my.log.****)的文件，并新建一个my.log，继续记录后续日志。
        (1) 重写TimedRotatingFileHandler的doRollover方法的文件翻转块代码
        做了以下两点改动：
            重定义了新文件名，将日期放在了中间而不是最后
            直接将baseFilename 指向新文件
        """
        if self.stream:
            self.stream.close()
            self.stream = None
        currentTime = int(time.time())
        dstNow = time.localtime(currentTime)[-1]

        log_type = 'info' if self.level == 20 else 'error'
        # 重新定义了新文件名
        base_dir = os.path.dirname(os.path.dirname(self.baseFilename))
        datetime_now = datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S').split('_')
        date_now = datetime_now[0]
        log_dir = os.path.join(base_dir,date_now)
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        dfn = os.path.join(log_dir,f"{log_type}.log")
        if os.path.exists(dfn):
            os.remove(dfn)
        self.baseFilename = dfn  # 直接将将baseFilename 指向新文件

        # if os.path.exists(dfn):
        #     os.remove(dfn)
        # self.rotate(self.baseFilename, dfn)
        if self.backupCount > 0:
            for s in self.getFilesToDelete():
                shutil.rmtree(s)
        if not self.delay:
            self.stream = self._open()
        newRolloverAt = self.computeRollover(currentTime)
        while newRolloverAt <= currentTime:
            newRolloverAt = newRolloverAt + self.interval
        # If DST changes and midnight or weekly rollover, adjust for this.
        if (self.when == 'MIDNIGHT' or self.when.startswith('W')) and not self.utc:
            dstAtRollover = time.localtime(newRolloverAt)[-1]
            if dstNow != dstAtRollover:
                if not dstNow:  # DST kicks in before next rollover, so we need to deduct an hour
                    addend = -3600
                else:  # DST bows out before next rollover, so we need to add an hour
                    addend = 3600
                newRolloverAt += addend
        self.rolloverAt = newRolloverAt
    def getFilesToDelete(self):
        """
        Determine the files to delete when rolling over.

        More specific than the earlier method, which just used glob.glob().
        """
        dirName = os.path.dirname(self.baseFilename)
        dirName, baseName = os.path.split(dirName)
        fileNames = os.listdir(dirName)
        result = []
        for fileName in fileNames:
            if self.extMatch.match(fileName):
                result.append(os.path.join(dirName, fileName))
        if len(result) < self.backupCount:
            result = []
        else:
            result.sort()
            result = result[:len(result) - self.backupCount]
        return result


class MyLogger(object):
    level_relations = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL
    }

    def __init__(self, name,log_dir,level="info",formatter="%(asctime)s [] [%(thread)d] %(levelname)s %(message)s",
                 when='D',backupCount=30):
        datetime_now = datetime.datetime.now().strftime('%Y-%m-%d_%H%M%S').split('_')
        date_now = datetime_now[0]

        log_dir = os.path.join(log_dir,date_now)
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        log_error_file = os.path.join(log_dir,"error.log")
        log_info_file = os.path.join(log_dir,"info.log")

        format_str = logging.Formatter(formatter,"%Y-%m-%d %H:%M:%S")
        streamHandler = logging.StreamHandler()
        streamHandler.setFormatter(format_str)


        error_file_handler = TimeLoggerRolloverHandler(filename=log_error_file, when=when, backupCount=backupCount,
                                                        encoding="utf-8")
        error_file_handler.addFilter(LogFilter.error_filter)
        error_file_handler.setFormatter(format_str)
        error_file_handler.setLevel(self.level_relations.get('error'))

        info_file_handel = TimeLoggerRolloverHandler(filename=log_info_file, when=when, backupCount=backupCount,
                                                        encoding="utf-8")
        info_file_handel.addFilter(LogFilter.info_filter)
        info_file_handel.setFormatter(format_str)
        info_file_handel.setLevel(self.level_relations.get('info'))

        self.logger = logging.getLogger(name)
        self.logger.setLevel(self.level_relations.get(level))
        self.logger.addHandler(streamHandler)
        self.logger.addHandler(error_file_handler)
        self.logger.addHandler(info_file_handel)
    def get_logger(self):
        return self.logger

logger = MyLogger(**LOG_CONF).get_logger()

# logging.disable(logging.DEBUG)  # 关闭DEBUG日志的打印
# logging.disable(logging.WARNING)  # 关闭WARNING日志的打印