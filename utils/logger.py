#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
@File    :   logger.py
@Time    :   2024/10/30 10:14:00
@Author  :   wbzhang 
@Version :   1.0
@Desc    :   日志记录
'''


import logging
from logging import Logger
import os


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


def get_logger(logger_name: str = "speech_scraper", log_filepath: str = None):
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)

    # 创建一个handler，用于写入日志文件
    if not log_filepath:
        log_filepath = "../log/"
        os.makedirs(log_filepath, exist_ok=True)
    fh = logging.FileHandler(log_filepath + "{}_scraper.log".format(logger_name))
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
