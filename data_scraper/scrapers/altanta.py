#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    :   altanta.py
@Time    :   2024/10/10 19:24:42
@Author  :   wbzhang
@Version :   1.0
@Desc    :   6F 亚特兰大联储行长讲话数据爬取
"""

import os
import sys
import time

sys.path.append("../../")
sys.path.append("../")

# from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup

from data_scraper.scrapers.scraper import SpeechScraper
from utils.common import parse_datestring
from utils.file_saver import json_load, json_update  # , json_dump
from utils.logger import get_logger


class AtlantaSpeechScraper(SpeechScraper):
    URL = "https://www.atlantafed.org/news/speeches"
    __fed_name__ = "atlanta"
    __name__ = f"{__fed_name__.title()}SpeechScraper"
    SAVE_PATH = f"../../data/fed_speeches/{__fed_name__}_fed_speeches/"

    logger = get_logger(
        logger_name=f"{__fed_name__}_speech_scraper", log_filepath="../../log/"
    )

    def __init__(self, url: str = None, auto_save: bool = True):
        super().__init__(url)
        self.speech_infos_by_year = None
        self.speeches_by_year = None
        os.makedirs(self.SAVE_PATH, exist_ok=True)
        print(f"{self.SAVE_PATH} has been created.")
        self.save = auto_save

    @staticmethod
    def parse_speaker(speech_content: WebElement):
        """解析演讲人元素

        Args:
            speech_content (WebElement): 演讲人元素

        Returns:
            tuple(str, str): 演讲人, 职位
        """
        try:
            # 演讲人元素
            speaker_element = speech_content.find_all("strong")
            assert len(speaker_element) != 0, "Speaker element not found"
            speaker_items = speaker_element[0].text.split("\n")
            # 演讲人
            speaker = speaker_items[0].strip() if len(speaker_items) > 0 else ""
            # 演讲人职位
            speaker_position = (
                speaker_items[1].strip() if len(speaker_items) > 1 else ""
            )
            return speaker, speaker_position
        except Exception as e:
            print(
                "Error when parsing speaker from speech content. {error}".format(
                    error=repr(e)
                )
            )
            return "", ""

    @staticmethod
    def parse_keypoints(speech_content: WebElement):
        """提取演讲正文中的亮点与正文

        Args:
            speech_content (WebElement): _description_

        Returns:
            _type_: _description_
        """
        try:
            # highlights
            keypoints = speech_content.find("ul")
            if keypoints:
                highlights = "\n\n".join(
                    [kp.text.strip() for kp in keypoints.find_all("li")]
                )
                # 剩下的兄弟节点才是正文内容
                content = "\n\n".join(
                    [p.text.strip() for p in keypoints.find_next_siblings("p")]
                )
            else:
                highlights = ""
                content = "\n\n".join(
                    [p.text.strip() for p in speech_content.find_all("p")[1:]]
                )
        except Exception as e:
            print(repr(e))
            highlights = ""
            content = ""
        return highlights, content

    def extract_single_speech(self, speech_info: dict):
        speech = {"speaker": "", "position": "", "highlights": "", "content": ""}
        try:
            self.driver.get(speech_info["href"])
            # 等待加载完
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located(
                    (
                        By.CSS_SELECTOR,
                        "body > div.container > article:nth-child(2) > section > div.row > div.col-lg-11 > div.card.card-default.content-object-control.border-0 > div.card-block > div.main-content",
                    )
                )
            )

            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, "html.parser")
            # 演讲内容元素
            speech_content = soup.find("div", class_="main-content")
            speaker, speaker_position = self.parse_speaker(speech_content)
            highlights, content = self.parse_keypoints(speech_content)
            speech = {
                "speaker": speaker,
                "position": speaker_position,
                "highlights": highlights,
                "content": content,
            }
        except Exception as e:
            print(
                "Error when extracting speech content from {href}. {error}".format(
                    href=speech_info["href"], error=repr(e)
                )
            )
            speech = {"speaker": "", "position": "", "highlights": "", "content": ""}
        speech.update(speech_info)
        return speech

    def extract_single_year_speech_infos(self, year: int):
        """提取某一年的讲话基本信息

        Args:
            year (int): 年份

        Returns:
            dict: list[dict]
        """
        # 选择年份
        select_element = Select(self.driver.find_element(By.ID, "YearList"))
        select_element.select_by_value(str(year))

        # 点击筛选按钮
        filter_button = self.driver.find_element(
            By.XPATH,
            "/html/body/div[1]/article[2]/section/div[2]/div[2]/div[2]/div/div/div[1]/form/div/div[2]/input[1]",
        )
        filter_button.click()
        # 等待加载完
        try:
            self.driver.implicitly_wait(3.0)
            WebDriverWait(self.driver, 10.0).until(
                EC.text_to_be_present_in_element(
                    (
                        By.XPATH,
                        "//div[@data-bind='foreach: items']",
                    ),
                    str(year),
                )
            )
        except TimeoutException as e:
            print("TimeoutException when filter button {}".format(year))
            filter_button.click()
            self.driver.implicitly_wait(3.0)
            WebDriverWait(self.driver, 10.0).until(
                EC.text_to_be_present_in_element(
                    (
                        By.XPATH,
                        "//div[@data-bind='foreach: items']",
                    ),
                    str(year),
                )
            )

        # 获取页面源码
        page_source = self.driver.page_source

        soup = BeautifulSoup(page_source, "html.parser")
        speech_infos = []

        # 查找包含演讲信息的 div 元素
        speech_container = soup.find(
            "div", class_="row frba-content_router-date-linked-headline-Teaser-grouped"
        )

        # 包含这一年所有文章的元素
        foreach_item = speech_container.find(
            "div", attrs={"data-bind": "foreach: items"}
        )
        # 取出所有元素
        dates = foreach_item.find_all("div", class_="font-weight-bold")
        title_links = foreach_item.find_all("a")
        highlights = foreach_item.find_all("p")

        for i in range(len(dates)):
            speech_info = {
                "date": dates[i].text.strip(),
                "title": title_links[i].text.strip(),
                "href": title_links[i]["href"],
                "highlights": highlights[i].text.strip(),
            }
            speech_infos.append(speech_info)

        return speech_infos

    def extract_speech_infos(self):
        """Extract speech infos from the website."""
        # 获取下拉框控件的所有选项
        years = [
            option.text.strip()
            for option in Select(self.driver.find_element(By.ID, "YearList")).options
            if option.text.strip().isdigit()
        ]

        speech_infos_by_year = {}
        for year in years:
            # print(f"Start scraping speeches of {year}...")
            if int(year) < 2006:
                continue
            single_year_speech_infos = self.extract_single_year_speech_infos(year)
            speech_infos_by_year[year] = single_year_speech_infos
            print(
                "{number} speeches of {year} was collected.".format(
                    number=len(speech_infos_by_year[year]), year=year
                )
            )
        json_update(
            self.SAVE_PATH + f"{self.__fed_name__}_speech_infos.json",
            speech_infos_by_year,
        )
        print(f"All speech infos of {self.__fed_name__} fetched and saved.")
        return speech_infos_by_year

    def extract_speeches(
        self, speech_infos_by_year: dict, start_date: str = "Jan 01, 2006"
    ):
        """搜集每篇演讲的内容"""
        # 获取演讲的开始时间
        start_date = parse_datestring(start_date)
        start_year = start_date.year

        speeches_by_year = {}
        failed = []
        for year, single_year_infos in speech_infos_by_year.items():
            if not year.isdigit():
                continue
            # 跳过之前的年份
            if int(year) < start_year:
                continue
            singe_year_speeches = []
            for speech_info in single_year_infos:
                if not speech_info["date"] or speech_info["date"] == "":
                    continue
                # 跳过start_date之前的演讲
                if parse_datestring(speech_info["date"]) <= start_date:
                    self.logger.info(
                        "Skip speech {date} {title} cause' it's earlier than start_date.".format(
                            date=speech_info["date"],
                            title=speech_info["title"],
                        )
                    )
                    continue
                single_speech = self.extract_single_speech(speech_info)
                if single_speech["content"] == "":
                    # 记录提取失败的报告
                    failed.append(single_speech)
                    print(
                        "Extract {date}, {title} failed.".format(
                            date=speech_info["date"],
                            title=speech_info["title"],
                        )
                    )
                singe_year_speeches.append(single_speech)
            speeches_by_year[year] = singe_year_speeches
            if self.save:
                json_update(
                    self.SAVE_PATH + f"{self.__fed_name__}_speeches_{year}.json",
                    singe_year_speeches,
                )
        if self.save:
            json_update(
                self.SAVE_PATH + f"{self.__fed_name__}_failed_speech_infos.json", failed
            )
            # json_update(
            #     self.SAVE_PATH + f"{self.__fed_name__}_speeches.json", speeches_by_year
            # )
        return speeches_by_year

    def update(self, year: str):
        """如何拉取更新的数据呢？

        记载最新的讲话数据，然后从网站获取最新讲话的时间，做判断.

        Args:
            year (_type_): _description_
        """
        # 已存储的最新报告日期
        if os.path.exists(self.SAVE_PATH + f"{self.__fed_name__}_speech_infos.json"):
            speech_infos = json_load(
                self.SAVE_PATH + f"{self.__fed_name__}_speech_infos.json"
            )
            latest_year = int(max(speech_infos.keys()))
            dates = [parse_datestring(sp["date"]) for sp in speech_infos[latest_year]]
            latest_speech_date = max(dates)
        else:
            latest_speech_date = None
        # 网页上最新的演讲日期（默认不点控件的第一个讲话）
        return latest_speech_date

    def collect(self):
        """收集每篇演讲的信息

        Returns:
            _type_: _description_
        """
        # 获取所有演讲信息
        speech_infos = self.extract_speech_infos()
        if self.save:
            json_update(
                self.SAVE_PATH + f"{self.__fed_name__}_speech_infos.json", speech_infos
            )

        # 查看已有的最新的演讲日期
        existed_speeches_filepath = (
            self.SAVE_PATH + f"{self.__fed_name__}_speeches.json"
        )
        if os.path.exists(existed_speeches_filepath):
            # 已存在的演讲日期
            existed_speeches = json_load(existed_speeches_filepath)
            # 按年整理的speeches
            speech_years = [k for k, _ in existed_speeches.items()]
            latest_year = max(speech_years)
            # 早于已存在日期的则不再收集.
            existed_lastest = max(
                [
                    parse_datestring(speech["date"])
                    for speech in existed_speeches[latest_year]
                ]
            ).strftime("%b %d, %Y")
        else:
            existed_lastest = "Jan 01, 2006"

        # 提取演讲内容
        speeches = self.extract_speeches(speech_infos, existed_lastest)
        if self.save:
            json_update(self.SAVE_PATH + f"{self.__fed_name__}_speeches.json", speeches)
        return speeches


def test_extract_speech_infos():
    """测试 extract_speeches 信息 方法"""
    scraper = AtlantaSpeechScraper()
    speech_infos = scraper.extract_speech_infos()
    print(speech_infos)


def test_extract_single_speech():
    """测试 extract_single_speech 方法"""
    scraper = AtlantaSpeechScraper()
    speech_info = {
        "date": "Jan 05, 2023",
        "title": "Understanding the Interplay between Financial Markets and Monetary Policy",
        "href": "https://www.atlantafed.org/news/speeches/2023/01/05/bostic-understanding-the-interplay-between-financial-markets-and-monetary-policy",
        "highlights": "Atlanta Fed president Raphael Bostic gives the opening remarks at the Day Ahead Conference on Financial Markets and Institutions on Thursday, January 5.",
    }

    # speech_info = {
    #     "date": "February 17, 2006",
    #     "title": "Taking into Account a Changing World of Banking",
    #     "href": "https://www.atlantafed.org/news/speeches/2006/060217-barron",
    #     "highlights": "",
    # }

    speech = scraper.extract_single_speech(speech_info)
    print(speech)


def test():
    scraper = AtlantaSpeechScraper()
    scraper.collect()


if __name__ == "__main__":
    # test_extract_single_speech()
    test()
