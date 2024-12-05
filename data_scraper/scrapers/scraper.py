#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    :   scraper.py
@Time    :   2024/10/31 09:31:30
@Author  :   wbzhang
@Version :   1.0
@Desc    :   演讲数据爬虫基类
"""

import os
from abc import abstractmethod
from selenium import webdriver

from utils.logger import get_logger

FOMC_MEETING_PROMPT = """
下面这个网站是美联储FOMC的会议网址：https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
该网址的正文部分按照自然年用Panel控件发布了每年的美联储议息会议的公告，包括会议月份和日期、议息决议Statement和会议备忘录Minutes。其中Statement给出了PDF、HTML以及Implementation Note三个链接，Minutes则只给出了PDF和HTML链接以及发布时间。注意，有的决议可能不披露上述信息，则仅保存月份、日期和决议名称等信息。
我想要按照年份，爬取每一条议息决议数据，包括月份、日期、statement中HTML的网址和内容，以及会议备忘录minutes中的内容，每一条决议数据都存储为一个字典，最后按年份来保存所有数据为json文件。
记载每一条议息决议的字典应当包含如下键，含义如下：
year: 决议年份，为str类型，如2024
month: 决议月份，为str类型，如Feb
date: 决议日期，为str类型，如17-19


请帮我基于Python和Selenium开发代码实现上述功能。
"""


class SpeechScraper(object):
    URL: str = ""
    __fed_name__ = ""
    __name__ = f"{__fed_name__.title()}SpeechScraper"

    def __init_driver(self, url: str, **kwargs):
        # 先进入主页
        print(
            "=" * 50
            + f" Opening the homepage of {self.__fed_name__.title()}. "
            + "=" * 50
            + "\n"
        )
        # chrome选项
        options = kwargs.get("options", None)
        self.driver = webdriver.Chrome(options=options)
        url = self.URL if url is None else url
        if not url:
            raise ValueError("No url provided.")
        self.driver.get(url)

    def __init__(self, url: str = None, auto_save: bool = True, **kwargs):
        # 自动保存
        self.save = auto_save
        # 预设存储路径
        output_dir = kwargs.get("output_dir", "../data/fed_speeches")
        self.SAVE_PATH = os.path.abspath(
            os.path.join(output_dir, f"{self.__fed_name__}_fed_speeches")
        )
        os.makedirs(self.SAVE_PATH, exist_ok=True)
        # 日志记录
        self.log_dir = os.path.abspath(kwargs.get("log_dir", "../log"))
        os.makedirs(self.log_dir, exist_ok=True)
        self.logger = get_logger(
            logger_name=f"{self.__fed_name__}_speech_scraper", log_filepath=self.log_dir
        )
        # 保存文件的文件名
        self.speech_infos_filename = os.path.join(
            self.SAVE_PATH, f"{self.__fed_name__}_speech_infos.json"
        )
        self.speeches_filename = os.path.join(
            self.SAVE_PATH, f"{self.__fed_name__}_speeches.json"
        )
        self.failed_speech_infos_filename = os.path.join(
            self.SAVE_PATH, f"{self.__fed_name__}_failed_speech_infos.json"
        )
        # 初始化浏览器
        self.__init_driver(url, **kwargs)

    @property
    def save_path(self):
        return self.SAVE_PATH

    @abstractmethod
    def extract_speech_infos(self):
        """抽取演讲的url信息

        Raises:
            NotImplementedError: _description_
        """
        raise NotImplementedError("Method `extract_speech_infos` not realized.")

    # 考虑对已存在的speech_infos做更新.
    def extract_incremental_speech_infos(self):
        """抽取增量演讲的url信息"""
        pass

    def extract_single_speech(self, speech_info: dict):
        """抽取单个演讲内容"""
        pass

    @abstractmethod
    def extract_speeches(self):
        """抽取演讲内容

        Raises:
            NotImplementedError: _description_
        """
        raise NotImplementedError("Method `extract_speeches` not realized.")

    @abstractmethod
    def collect(self):
        """收集演讲并保存

        Raises:
            NotImplementedError: _description_
        """
        raise NotImplementedError("Method `collect` not realized.")
