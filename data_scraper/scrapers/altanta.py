#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    :   altanta.py
@Time    :   2024/10/10 19:24:42
@Author  :   wbzhang
@Version :   1.0
@Desc    :   亚特兰大官员讲话数据爬取
"""

import os
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from bs4 import BeautifulSoup
import time

from data_scraper.scrapers.scraper import SpeechScraper
from utils.common import parse_datestring
from utils.file_saver import json_dump, json_load


class AtlantaSpeechScraper(SpeechScraper):
    URL = "https://www.atlantafed.org/news/speeches"
    __fed_name__ = "atlanta"
    __name__ = f"{__fed_name__.title()}SpeechScraper"
    SAVE_PATH = f"../../data/fed_speeches/{__fed_name__}_fed_speeches/"

    def __init__(self, url: str = None, auto_save: bool = True):
        super().__init__(url)
        self.speech_infos_by_year = None
        self.speeches_by_year = None
        os.makedirs(self.SAVE_PATH, exist_ok=True)
        print(f"{self.SAVE_PATH} has been created.")
        self.save = auto_save

    @staticmethod
    def parse_speaker(speech_content):
        try:
            # 演讲人元素
            speaker_element = speech_content.find("p").find("strong")
            speaker_items = speaker_element.text.split("\n")
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
    def parse_keypoints(speech_content):
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

    def extract_single_year_speech_infos(self, year):
        # 选择年份
        select_element = Select(self.driver.find_element(By.ID, "YearList"))
        select_element.select_by_value(str(year))

        # 点击筛选按钮
        filter_button = self.driver.find_element(
            By.XPATH,
            "/html/body/div[1]/article[2]/section/div[2]/div[2]/div[2]/div/div/div[1]/form/div/div[2]/input[1]",
        )
        filter_button.click()

        self.driver.implicitly_wait(2)
        time.sleep(2)
        # 等待加载完
        WebDriverWait(self.driver, 3).until(
            EC.presence_of_all_elements_located(
                (
                    By.CLASS_NAME,
                    "row.frba-content_router-date-linked-headline-Teaser-grouped",
                )
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
            int(option.text)
            for option in Select(self.driver.find_element(By.ID, "YearList")).options
            if option.text.isdigit()
        ]

        speech_infos_by_year = {}
        for year in years:
            print(f"Start scraping speeches of {year}...")
            single_year_speech_infos = self.extract_single_year_speech_infos(year)
            speech_infos_by_year[year] = single_year_speech_infos
            print(f"Fetched speeches for {year}")
        json_dump(
            speech_infos_by_year,
            self.SAVE_PATH + f"{self.__fed_name__}_speech_infos.json",
        )
        print(f"All speech infos of {self.__fed_name__} fetched and saved.")
        return speech_infos_by_year

    def extract_speeches(self, speech_infos_by_year: dict):
        """搜集每篇演讲的内容"""
        speeches_by_year = {}
        failed = []
        for year, single_year_infos in speech_infos_by_year.items():
            singe_year_speeches = []
            for speech_info in single_year_infos:
                single_speech = self.extract_single_speech(speech_info)
                if single_speech["content"] == "":
                    # 记录提取失败的报告
                    failed.append(single_speech)
                singe_year_speeches.append(single_speech)
            speeches_by_year[year] = singe_year_speeches
            if self.save:
                json_dump(
                    singe_year_speeches,
                    self.SAVE_PATH + f"{self.__fed_name__}_speeches_{year}.json",
                )
        if self.save:
            json_dump(
                failed, self.SAVE_PATH + f"{self.__fed_name__}_failed_speech_infos.json"
            )
            json_dump(
                speeches_by_year, self.SAVE_PATH + f"{self.__fed_name__}_speeches.json"
            )
        return speeches_by_year

    def update(self, year):
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
        # 提取每年演讲的信息，若存在则不再更新？.做更新机制.
        if os.path.exists(self.SAVE_PATH + f"{self.__fed_name__}_speech_infos.json"):
            speech_infos = json_load(
                self.SAVE_PATH + f"{self.__fed_name__}_speech_infos.json"
            )
            print("Speech Infos Data already exists, skip collecting.")
        else:
            speech_infos = self.extract_speech_infos()
            if self.save:
                json_dump(
                    speech_infos,
                    self.SAVE_PATH + f"{self.__fed_name__}_speech_infos.json",
                )

        # 提取演讲内容
        speeches = self.extract_speeches(speech_infos)
        if self.save:
            json_dump(speeches, self.SAVE_PATH + f"{self.__fed_name__}_speeches.json")
        return speeches


def test_extract_single_speech():
    """测试 extract_single_speech 方法"""
    scraper = AtlantaSpeechScraper()
    speech_info = {
        "date": "Jan 05, 2023",
        "title": "Understanding the Interplay between Financial Markets and Monetary Policy",
        "href": "https://www.atlantafed.org/news/speeches/2023/01/05/bostic-understanding-the-interplay-between-financial-markets-and-monetary-policy",
        "highlights": "Atlanta Fed president Raphael Bostic gives the opening remarks at the Day Ahead Conference on Financial Markets and Institutions on Thursday, January 5.",
    }

    speech = scraper.extract_single_speech(speech_info)
    print(speech)


def test_extract_speech_infos():
    """测试 extract_speeches 信息 方法"""
    scraper = AtlantaSpeechScraper()
    speech_infos = scraper.extract_speech_infos()
    print(speech_infos)


def test():
    scraper = AtlantaSpeechScraper()
    scraper.collect()


if __name__ == "__main__":
    test()
