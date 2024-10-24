#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    :   dallas.py
@Time    :   2024/10/23 11:23:10
@Author  :   wbzhang
@Version :   1.0
@Desc    :   达拉斯联储银行讲话数据爬取
"""

import os
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webelement import WebElement
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
    NoSuchElementException,
)

from bs4 import BeautifulSoup
import time
from datetime import datetime

from data_scraper.scrapers.scraper import SpeechScraper
from utils.common import parse_datestring
from utils.file_saver import json_dump, json_load, json_update
from utils.logger import logger

SWORN_DATE_MAPPING = {"Lorie K. Logan": "August 22, 2022"}


class DallasSpeechScraper(SpeechScraper):
    URL = "https://www.dallasfed.org/news/speeches"
    __fed_name__ = "dallas"
    __name__ = f"{__fed_name__.title()}SpeechScraper"
    SAVE_PATH = f"../../data/fed_speeches/{__fed_name__}_fed_speeches/"

    def __init__(self, url: str = None, auto_save: bool = True):
        super().__init__(url)
        self.speech_infos_by_year = None
        self.speeches_by_year = None
        os.makedirs(self.SAVE_PATH, exist_ok=True)
        print(f"{self.SAVE_PATH} has been created.")
        self.save = auto_save

    def fetch_single_speech_info(self, speech_item: WebElement):
        """提取单个演讲元素的信息

        Args:
            speech_item (_type_): _description_
        """
        # 概要
        paras = re.split(r"[\n\"·]+", speech_item.text)
        # desc = paras[1].strip()
        # 日期
        date = ""
        for para in paras:
            parse_date = parse_datestring(para.split('·')[0].strip(' \n'))
            if isinstance(parse_date, datetime):
                date = para
            else:
                continue
        if date == "":
            print(paras[-1])
        # 标题
        title_element = speech_item.find_elements(By.XPATH, ".//a[@href]")
        if title_element:
            title = title_element[0].text.strip()
            href = title_element[0].get_attribute("href")
        else:
            title = paras[0]
            href = ""

        return {"date": date, "title": title, "href": href}  #  "desc": desc,

    def extract_speaker_name(self, text: str):
        pattern = r"President\s+(.*?)(?=\()"

        match = re.search(pattern, text)
        if match:
            result = match.group(1)
            return result.strip()
        else:
            return 'Unknown'
        

    def extract_speech_infos(self):
        """抽取演讲的信息"""
        # 搜寻每一个阶段的链接
        links = self.driver.find_elements(
            By.XPATH, "//*[@id='content']/div/div/ul/li/a[@href]"
        )
        links = {ele.text: ele.get_attribute("href") for ele in links}

        # 主循环获取所有演讲信息
        speech_infos_by_year = {}
        for title, link in links.items():
            # 提取主席作为speaker
            speaker = self.extract_speaker_name(title) 
            # 只抽取历任主席的讲话
            if "President" not in title:
                continue
            # 打开网站
            self.driver.get(link)
            WebDriverWait(self.driver, 10).until(
                EC.visibility_of_all_elements_located((By.ID, "dal-tabs"))
            )
            time.sleep(1.2)

            # 搜集所有tab页
            tab_buttons = self.driver.find_elements(
                By.XPATH, "//*[@id='dal-tabs']/div/ul/li/a[@href]"
            )
            # 对于每一个tab页分别搜集
            for tab in tab_buttons:
                # 点击tab页
                if tab.get_attribute("aria-selected") != "true":
                    tab.click()

                year = tab.text.strip()
                if year not in speech_infos_by_year:
                    speech_infos_by_year[year] = []
                # 找到当前所有的演讲元素
                speech_items = self.driver.find_elements(
                    By.XPATH, "//*[@id='{}']/p".format(year)
                )
                for item in speech_items:
                    speech_info = self.fetch_single_speech_info(item)
                    speech_info.update({"speaker": speaker})
                    # 从日期中获取年份
                    if speech_info["date"]!="":
                        true_year = str(parse_datestring(speech_info["date"]).year)
                    else:
                        true_year = year
                    # 仅保留在达拉斯任职时期的演讲
                    if speech_info["href"].startswith("https://www.dallasfed.org/"):
                        speech_infos_by_year.setdefault(true_year, []).append(
                            speech_info
                        )

        self.speech_infos_by_year = speech_infos_by_year
        return speech_infos_by_year

    def extract_single_speech(self, speech_info: dict):
        speech = {"speaker": "", "position": "", "highlights": "", "content": ""}
        try:
            self.driver.get(speech_info["href"])
            # 等待加载完
            WebDriverWait(self.driver, 10).until(
                EC.visibility_of_all_elements_located((By.ID, "content"))
            )
            time.sleep(1.2)

            # 主内容元素
            main_content = self.driver.find_element(By.ID, "content")
            paragraph_elements = main_content.find_elements(
                By.XPATH,
                ".//div[contains(@class, 'dal-main-content')]/h3|.//div[contains(@class, 'dal-main-content')]/p",
            )
            if paragraph_elements:
                content = "\n\n".join([p.text.strip() for p in paragraph_elements])
                print(
                    "{} {} {} content extracted.".format(
                        speech_info["speaker"],
                        speech_info["date"],
                        speech_info["title"],
                    )
                )
            else:
                content = ""
                print(
                    "{} {} {} content failed.".format(
                        speech_info["speaker"],
                        speech_info["date"],
                        speech_info["title"],
                    )
                )

            speech = {"content": content}
        except Exception as e:
            print(
                "Error when extracting speech content from {href}. {error}".format(
                    href=speech_info["href"], error=repr(e)
                )
            )
            speech = {"content": ""}
            print(
                "{} {} {} content failed.".format(
                    speech_info["speaker"], speech_info["date"], speech_info["title"]
                )
            )
        speech.update(speech_info)
        return speech

    def extract_speeches(
        self, speech_infos_by_year: dict, start_date: str = "Jan 01, 2006"
    ):
        """搜集每篇演讲的内容"""
        # 获取演讲的开始时间
        start_date = parse_datestring(start_date)
        start_year = start_date.year

        # 获取每年的演讲内容
        speeches_by_year = {}
        failed = []
        for year, single_year_infos in speech_infos_by_year.items():
            if not year.isdigit():
                continue
            # 跳过之前的年份
            if int(year) < start_year:
                continue
            single_year_speeches = []
            for speech_info in single_year_infos:
                # 跳过start_date之前的演讲
                if parse_datestring(speech_info["date"]) <= start_date:
                    logger.info(
                        "Skip speech {speaker} {date} {title} cause' it's earlier than start_date.".format(
                            speaker=speech_info["speaker"],
                            date=speech_info["date"],
                            title=speech_info["title"],
                        )
                    )
                    continue
                # 提取演讲正文
                single_speech = self.extract_single_speech(speech_info)
                if single_speech["content"] == "":
                    # 记录提取失败的报告
                    failed.append(single_speech)
                    logger.warning(
                        "Extract {speaker} {date} {title}".format(
                            speaker=speech_info["speaker"],
                            date=speech_info["date"],
                            title=speech_info["title"],
                        )
                    )
                single_year_speeches.append(single_speech)
            speeches_by_year[year] = single_year_speeches
            if self.save:
                json_update(
                    self.SAVE_PATH + f"{self.__fed_name__}_speeches_{year}.json",
                    single_year_speeches,
                )
            print(f"Speeches of {year} collected.")
        # 保存演讲内容
        if self.save:
            # 保存读取失败的演讲内容
            json_dump(
                failed, self.SAVE_PATH + f"{self.__fed_name__}_failed_speech_infos.json"
            )
            # 更新已存储的演讲内容
            json_update(
                self.SAVE_PATH + f"{self.__fed_name__}_speeches.json", speeches_by_year
            )
        return speeches_by_year

    def collect(self):
        """收集每篇演讲的信息

        Returns:
            _type_: _description_
        """
        # 提取每年演讲的基本信息（不含正文和highlights等）
        if os.path.exists(self.SAVE_PATH + f"{self.__fed_name__}_speech_infos.json"):
            speech_infos = json_load(
                self.SAVE_PATH + f"{self.__fed_name__}_speech_infos.json"
            )
            # 查看已有的最新的演讲日期
            latest_year = max([k for k, _ in speech_infos.items()])
            existed_lastest = max(
                [
                    parse_datestring(speech_info["date"])
                    for speech_info in speech_infos[latest_year]
                ]
            ).strftime("%b %d, %Y")
            logger.info("Speech Infos Data already exists, skip collecting infos.")
            existed_lastest = "Jan 01, 2006"
        else:
            speech_infos = self.extract_speech_infos()
            if self.save:
                json_dump(
                    speech_infos,
                    self.SAVE_PATH + f"{self.__fed_name__}_speech_infos.json",
                )
            existed_lastest = "Jan 01, 2006"

        # 提取演讲正文内容
        speeches = self.extract_speeches(speech_infos, existed_lastest)
        return speeches


def test_extract_speech_infos():
    """测试 extract_speeches 信息 方法"""
    scraper = DallasSpeechScraper()
    speech_infos = scraper.extract_speech_infos()
    print(speech_infos)


def test_extract_single_speech():
    """测试 extract_single_speech 方法"""
    scraper = DallasSpeechScraper()
    speech_info = {
        "date": "August 21, 2018",
        "title": "Where We Stand: Assessment of Economic Conditions and Implications for Monetary Policy",
        "href": "https://www.dallasfed.org/news/speeches/kaplan/2018/rsk180821.aspx",
        "speaker": "Robert S. Kaplan",
    }

    speech = scraper.extract_single_speech(speech_info)
    print(speech)


def test():
    scraper = DallasSpeechScraper()
    scraper.collect()


if __name__ == "__main__":
    # test_extract_speech_infos()
    # test_extract_single_speech()
    test()
