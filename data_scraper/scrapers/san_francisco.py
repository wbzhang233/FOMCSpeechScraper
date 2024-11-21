#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    :   san_francisco.py
@Time    :   2024/09/30 15:02:17
@Author  :   wbzhang
@Version :   1.0
@Desc    :   12L 旧金山联储历任主席讲话数据爬取
"""

import os
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
    NoSuchElementException,
)

from bs4 import BeautifulSoup
import time

from data_scraper.scrapers.scraper import SpeechScraper
from utils.common import parse_datestring
from utils.file_saver import json_dump, json_load, json_update


class SanFranciscoSpeechScraper(SpeechScraper):
    URL = "https://www.frbsf.org/news-and-media/speeches/"
    __fed_name__ = "sanfrancisco"
    __name__ = f"{__fed_name__.title()}SpeechScraper"
    SAVE_PATH = f"../../data/fed_speeches/{__fed_name__}_fed_speeches/"

    def __init__(self, url: str = None, auto_save: bool = True):
        super().__init__(url)
        self.speech_infos_by_year = None
        self.speeches_by_year = None
        os.makedirs(self.SAVE_PATH, exist_ok=True)
        print(f"{self.SAVE_PATH} has been created.")
        self.save = auto_save

    def extract_speech_infos(self):
        """抽取演讲的信息"""
        # 主循环获取所有演讲信息
        speech_infos_by_year = {}
        while True:
            soup = BeautifulSoup(self.driver.page_source, "html.parser")
            speech_items = soup.find_all("div", class_="fwpl-result")

            for item in speech_items:
                # 提取日期
                date = item.find("div", class_=["fwpl-item el-julyf"]).text.strip()
                year = date.split(",")[-1].strip()
                if year not in speech_infos_by_year:
                    speech_infos_by_year[year] = []
                # 提取演讲者
                speaker_element = item.find(
                    "span",
                    class_=re.compile("fwpl-term.*fwpl-tax-speech-series"),
                )
                if speaker_element:
                    speaker = speaker_element.text.strip()
                    speaker = re.sub(r"['’]*s* Speeches", "", speaker)
                else:
                    speaker = ""

                # 提取标题和链接
                title_link = item.find("a", href=True)
                title = title_link.text.strip()
                href = title_link["href"]

                # 提取演讲地点
                location_element = item.find(
                    "div",
                    class_=re.compile("fwpl-item.*el-6d47we.*wp-block-post-excerpt"),
                )
                location = location_element.text.strip() if location_element else ""

                speech_infos_by_year[year].append(
                    {
                        "date": date,
                        "speaker": speaker,
                        "title": title,
                        "href": href,
                        "location": location,
                    }
                )

            # # Try to find and click the "Next" button
            try:
                next_button = self.driver.find_element(
                    By.CSS_SELECTOR, "a.facetwp-page.next:not(.disabled)"
                )
                self.driver.execute_script("arguments[0].click();", next_button)
                # 等待页面加载
                time.sleep(2.0)
            except NoSuchElementException as e:
                print(
                    f"Next button not found or disabled. Reached last page. {repr(e)}"
                )
                break
            except TimeoutException as e:
                print(
                    f"Next button not found or disabled. Reached last page. {repr(e)}"
                )
                break
            except WebDriverException as e:
                print(
                    f"Next button not found or disabled. Reached last page. {repr(e)}"
                )
                break

        self.speech_infos_by_year = speech_infos_by_year
        if self.save:
            json_dump(
                speech_infos_by_year,
                self.SAVE_PATH + f"{self.__fed_name__}_speech_infos.json",
            )
        return speech_infos_by_year

    def extract_single_speech(self, speech_info: dict):
        speech = {"speaker": "", "position": "", "highlights": "", "content": ""}
        try:
            self.driver.get(speech_info["href"])
            # 等待加载完
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "wp--skip-link--target"))
            )

            # 主内容元素
            main_content = self.driver.find_element(By.ID, "wp--skip-link--target")
            content_element = main_content.find_element(
                By.CSS_SELECTOR,
                "div.entry-content.wp-block-post-content.has-global-padding.is-layout-constrained > div > div.sffed-main-content.wp-block-column.sffed-heading--greycliff.is-layout-flow.wp-block-column-is-layout-flow > div",
            )
            if content_element:
                content = "\n\n".join(
                    [
                        p.text.strip()
                        for p in content_element.find_elements(By.TAG_NAME, "p")
                    ]
                )
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
        speech_info.update(speech)
        return speech_info

    def extract_speeches(self, speech_infos_by_year: dict, start_date: str):
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
                    print(
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
                singe_year_speeches.append(single_speech)
            speeches_by_year[year] = singe_year_speeches
            if self.save:
                json_update(
                    self.SAVE_PATH + f"{self.__fed_name__}_speeches_{year}.json",
                    singe_year_speeches
                )
            print(f"Speeches of {year} collected.")
        if self.save:
            json_dump(
                failed, self.SAVE_PATH + f"{self.__fed_name__}_failed_speech_infos.json"
            )
            json_update(
                self.SAVE_PATH + f"{self.__fed_name__}_speeches.json",
                speeches_by_year,
            )
        return speeches_by_year

    # def update(self, latest_date: str):
    # 获取最新的演讲的日期，如果演讲日期与页面上演讲日期不一致，则更新最新演讲日期之后的报告
    # if os.path.exists(self.SAVE_PATH + f"{self.__fed_name__}_speech_infos.json"):
    #     speech_infos = json_load(
    #         self.SAVE_PATH + f"{self.__fed_name__}_speech_infos.json"
    #     )
    #     print("Speech Infos Data already exists, skip collecting.")
    #     # 获取

    def collect(self):
        """收集每篇演讲的信息

        Returns:
            _type_: _description_
        """
        # 提取每年演讲的信息，若存在则不再更新？.做更新机制.
        # if os.path.exists(self.SAVE_PATH + f"{self.__fed_name__}_speech_infos.json"):
        #     speech_infos = json_load(
        #         self.SAVE_PATH + f"{self.__fed_name__}_speech_infos.json"
        #     )
        #     print("Speech Infos Data already exists, skip collecting.")
        # else:
        speech_infos = self.extract_speech_infos()
        if self.save:
            json_update(
                self.SAVE_PATH + f"{self.__fed_name__}_speech_infos.json",
                speech_infos,
            )
        existed_lastest = "Jun 24, 2024"

        # 提取演讲内容
        speeches = self.extract_speeches(speech_infos, existed_lastest)
        if self.save:
            json_update(self.SAVE_PATH + f"{self.__fed_name__}_speeches.json", speeches)
        return speeches


def test_extract_single_speech():
    """测试 extract_single_speech 方法"""
    scraper = SanFranciscoSpeechScraper()
    speech_info = {
        "content": "",
        "date": "Mary C. Daly’s Speeches",
        "speaker": "Mary C. Daly’s Speeches",
        "title": "Version Two",
        "href": "https://www.frbsf.org/news-and-media/speeches/mary-c-daly/2024/05/version-two",
        "location": "Mary C. Daly’s Speeches",
    }

    speech = scraper.extract_single_speech(speech_info)
    print(speech)


def test_extract_speech_infos():
    """测试 extract_speeches 信息 方法"""
    scraper = SanFranciscoSpeechScraper()
    speech_infos = scraper.extract_speech_infos()
    print(speech_infos)


def test():
    scraper = SanFranciscoSpeechScraper()
    scraper.collect()


if __name__ == "__main__":
    # test_extract_speech_infos()
    # test_extract_single_speech()
    test()
