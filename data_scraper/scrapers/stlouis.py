#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    :   stlouis.py
@Time    :   2024/10/29 15:25:47
@Author  :   wbzhang
@Version :   1.0
@Desc    :   圣路易斯联储主席讲话数据爬虫
"""

import os
import time
import re
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
    NoSuchElementException,
)
from selenium.webdriver.remote.webelement import WebElement
from data_scraper.scrapers.scraper import SpeechScraper
from freser_scraper import FRESERScraper
from utils.common import parse_datestring
from utils.file_saver import json_dump, json_load, json_update
from utils.logger import logger


class StLouisSpeechScraper(SpeechScraper):
    URL = "https://fraser.stlouisfed.org/series/statements-speeches-presidents-federal-reserve-bank-st-louis-3767"
    __fed_name__ = "stlouis"
    __name__ = f"{__fed_name__.title()}SpeechScraper"
    SAVE_PATH = f"../../data/fed_speeches/{__fed_name__}_fed_speeches/"

    def __init__(self, url: str = None, auto_save: bool = True):
        super().__init__(url)
        self.speech_infos_by_year = None
        self.speeches_by_year = None
        os.makedirs(self.SAVE_PATH, exist_ok=True)
        print(f"{self.SAVE_PATH} has been created.")
        self.save = auto_save

    def fetch_series_all_titles(self):
        """提取FRESER上某个series的所有子title

        Args:
            speech_item (_type_): _description_
        """
        title_infos = []
        # 打开圣路易斯联储讲话集合
        self.driver.get(self.URL)
        titles = self.driver.find_elements(
            By.XPATH, "//ul[@class='browse-by-list']/li"
        )  # /span
        for title in titles:
            title.click()
            WebDriverWait(self.driver, 10).until(
                EC.visibility_of_all_elements_located(
                    (By.XPATH, "//div[contains(@class, 'browse-by-right')]")
                )
            )
            self.driver.implicitly_wait(2)
            # wait = WebDriverWait(self.driver, timeout=2)
            # wait.until(lambda d: title.is_displayed())
            time.sleep(1.0)
            # 名称
            title_name = title.text

            # 获取链接
            try:
                # 切换对话窗
                dialog = self.driver.find_element(
                    By.XPATH, "//div[@class='modal-dialog' and @role='document']"
                )

                # 获取title链接
                # button = dialog.find_elements(
                #     By.XPATH, ".//a[@href and (contains(@class, 'btn btn-success'))]"
                # )
                # if button:
                #     href = button[0].get_attribute("href")
                # else:
                #     href = ''
                # 获取该series下的所有title_id
                # href = FRESERScraper.fetch_by_title(title_id=3767)
                href = dialog.find_element(
                    By.XPATH, "//input[@id='share-url' and @value]"
                ).get_attribute("value")
                # title-id
                title_id = href.split("/")[-1]
            except Exception as e:
                msg = "Error when fetching series titles: {}".format(repr(e))
                print(msg)
                href = None
                title_id = None
            title_infos.append(
                {"title": title_name, "href": href, "title_id": title_id}
            )
        return title_infos

    def collect_title_all_issues(self, title_info: str):
        """搜集某个title下所有讲话的文本数据

        Args:
            title_link (str): _description_
        """
        # 搜集每个讲话的数据, 直接使用title-toc接口获取
        result = FRESERScraper.fecth_title_toc(title_id=int(title_info["title_id"]))
        if not result or len(result)==0:
            # 开始爬取每篇报告的text_url
            self.driver.get(title_info['href'])
            # 找到所有条目，搜集链接
            items = self.driver.find_elements(
                By.XPATH,
                ""
            )
            result = []
            for item in items:
                # 标题
                item_name = item.text.strip()
                # 链接
                item_link = item.get_attribute('value')
                item_id = item_link.split('#')[-1]
                if item_id.isdigit():
                    # 打开链接，找到下载按键 -> 找到text_url，获取
                    content = FRESERScraper.fecth_item(item_id=int(item_id))
                    # 获取作者 namePart
                    # 获取日期 dateIssued
                else:
                    content = ''
                result.append(
                    {
                        "title": item_name,
                        "href": item_link,
                        "item_id": item_id,
                        "content": content,
                        "speaker": "",
                        "date": ""
                    }
                )

        return result

    def extract_speech_infos(self):
        """抽取演讲的信息"""
        # 搜寻历任主席的title链接
        if os.path.exists(self.SAVE_PATH + f"{self.__fed_name__}_title_infos.json"):
            title_infos = json_load(
                self.SAVE_PATH + f"{self.__fed_name__}_title_infos.json"
            )
        else:
            title_infos = self.fetch_series_all_titles()
            json_dump(
                title_infos, self.SAVE_PATH + f"{self.__fed_name__}_title_infos.json"
            )
        # 对每一个进行搜集
        speech_infos_by_year = None
        for title_info in title_infos:
            self.collect_title_all_issues(title_info=title_info)

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
            existed_lastest = "Jan 01, 2024"
        else:
            speech_infos = self.extract_speech_infos()
            if self.save:
                json_dump(
                    speech_infos,
                    self.SAVE_PATH + f"{self.__fed_name__}_speech_infos.json",
                )
            existed_lastest = "Jan 01, 2006"

        # 提取演讲正文内容
        print("-" * 100)
        print("Extract speeches start from {}".format(existed_lastest))
        print("-" * 100)
        speeches = self.extract_speeches(speech_infos, existed_lastest)
        return speeches


def test_extract_speech_infos():
    """测试 extract_speeches 信息 方法"""
    scraper = StLouisSpeechScraper()
    speech_infos = scraper.extract_speech_infos()
    print(speech_infos)


def test_extract_single_speech():
    """测试 extract_single_speech 方法"""
    scraper = StLouisSpeechScraper()
    speech_info = {
        "date": "August 21, 2018",
        "title": "Where We Stand: Assessment of Economic Conditions and Implications for Monetary Policy",
        "href": "https://www.dallasfed.org/news/speeches/kaplan/2018/rsk180821.aspx",
        "speaker": "Robert S. Kaplan",
    }

    speech = scraper.extract_single_speech(speech_info)
    print(speech)


def test():
    scraper = StLouisSpeechScraper()
    scraper.collect()


if __name__ == "__main__":
    # test_extract_speech_infos()
    # test_extract_single_speech()
    test()
