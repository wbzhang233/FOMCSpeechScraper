import logging
from logging import Logger


class ScraperLogger(Logger):
    def __init__(self, name: str, level=logging.INFO):
        super().__init__(name=name, level=level)
        # 创建一个logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        # 创建一个handler，用于写入日志文件
        self.fh = logging.FileHandler("{}_scraper.log".format(name))
        self.fh.setLevel(logging.DEBUG)

        # 再创建一个handler，用于输出到控制台
        self.ch = logging.StreamHandler()
        self.ch.setLevel(logging.ERROR)

        # 定义handler的输出格式
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        self.fh.setFormatter(formatter)
        self.ch.setFormatter(formatter)

        # 给logger添加handler
        self.logger.addHandler(self.fh)
        self.logger.addHandler(self.ch)


def setup_logger(name: str, log_file: str = None, level=logging.INFO):
    """Function to setup as many loggers as you want"""
    if not log_file:
        log_file = "{}_scraper.log".format(name)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler = logging.FileHandler(log_file)
    handler.setFormatter(formatter)

    logger = ScraperLogger(name, level)
    logger.addHandler(handler)

    return logger


def get_logger(logger_name: str = "speech_scraper"):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)

    # 创建一个handler，用于写入日志文件
    fh = logging.FileHandler("{}_scraper.log".format(logger_name))
    fh.setLevel(logging.DEBUG)

    # 再创建一个handler，用于输出到控制台
    ch = logging.StreamHandler()
    ch.setLevel(logging.ERROR)

    # 定义handler的输出格式
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    # 给logger添加handler
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


# logger = ScraperLogger()
logger = get_logger()


def test_get_logger():
    # logger.info("Test logger usage.")
    loggger = ScraperLogger("Boston")
    loggger.info("Boston")
    print("Done")


if __name__ == "__main__":
    test_get_logger()
