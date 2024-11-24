#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    :   board.py
@Time    :   2024/11/19 16:36:10
@Author  :   wbzhang
@Version :   1.0
@Desc    :   理事会成员讲话稿数据爬取
"""

from copy import deepcopy
import os
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    # TimeoutException,
    # WebDriverException,
    NoSuchElementException,
)

import time
from datetime import datetime

from data_scraper.scrapers.scraper import SpeechScraper
from utils.common import parse_datestring
from utils.file_saver import json_dump, json_load, json_update, sort_speeches_dict
from utils.logger import logger

today = datetime.today().date()


class BOGSpeechScraper(SpeechScraper):
    URL = "https://www.federalreserve.gov/newsevents/speeches.htm"
    __fed_name__ = "bog"
    __name__ = f"{__fed_name__.title()}SpeechScraper"
    SAVE_PATH = f"../../data/fed_speeches/{__fed_name__}_fed_speeches/"

    def __init__(
        self,
        start_date: str = None,
        end_date: str = None,
        url: str = None,
        auto_save: bool = True,
        **kwargs,
    ):
        super().__init__(url)
        self.speech_infos_by_year = None
        self.speeches_by_year = None
        os.makedirs(self.SAVE_PATH, exist_ok=True)
        print(f"{self.SAVE_PATH} has been created.")
        self.save = auto_save
        # 起止时间
        self.start_date = (
            pd.to_datetime(start_date).date()
            if start_date
            else datetime(2006, 1, 1).date()
        )
        self.end_date = pd.to_datetime(end_date).date() if end_date else today
        # 保存文件的文件名
        self.speech_infos_filename = (
            self.SAVE_PATH + f"{self.__fed_name__}_speech_infos.json"
        )
        self.speeches_filename = (
            self.SAVE_PATH + f"{self.__fed_name__}_fed_speeches.json"
        )
        self.failed_speech_infos_filename = (
            self.SAVE_PATH + f"{self.__fed_name__}_failed_speech_infos.json"
        )

    def get_speech_links_from_current_page(self, speech_infos_by_year: dict):
        """搜集当前页面的所有演讲链接

        Returns:
            (list): 演讲链接列表
        """
        try:
            # 逐个查找
            row = self.driver.find_element(
                By.XPATH,
                '//*[@id="article"]/div[1]/div[(@class="row ng-scope") and (contains(@ng-repeat, "item in items"))]',
            )
            while True:
                try:
                    # 演讲稿链接
                    link = row.find_element(By.CSS_SELECTOR, "p.itemTitle em a")
                    href = link.get_attribute("href")
                    # 标题
                    title = link.text.strip()
                    # 日期
                    date = row.find_element(By.CSS_SELECTOR, "time").text.strip()
                    # 演讲人
                    speaker = row.find_element(
                        By.CLASS_NAME, "news__speaker.ng-binding"
                    ).text.strip()

                    if (
                        pd.to_datetime(date).date() >= self.start_date
                        or pd.to_datetime(date).date() <= self.end_date
                    ):
                        date = pd.to_datetime(date)
                        date_str = date.strftime("%B %d, %Y")
                        year_str = date.strftime("%Y")
                        # article > div.angularEvents.items.ng-scope > div:nth-child(2) > div.col-xs-3.col-md-2.eventlist__time > time
                        speech_infos_by_year.setdefault(year_str, []).append(
                            {
                                "speaker": speaker,
                                "date": date_str,
                                "title": title,
                                "href": href,
                            }
                        )
                    following_siblings = row.find_elements(
                        By.XPATH,
                        'following-sibling::div[(@class="row ng-scope") and (contains(@ng-repeat, "item in items"))]',
                    )
                    if not following_siblings or len(following_siblings) == 0:
                        break
                    row = following_siblings[0]
                except NoSuchElementException:
                    print("Could not find link or date in a row. Skipping.")
            return speech_infos_by_year
        except Exception as e:
            print(f"Error extracting speech URLs from the current page: {e}")
            return speech_infos_by_year

    def extract_speech_infos(self):
        """抽取演讲的信息"""
        # 设置筛选时间
        # Locate the start and end date input fields and set the desired dates
        start_date_elem = self.driver.find_element(
            By.XPATH,
            '//*[@id="content"]/div[2]/div/div[1]/form/div[2]/div/div[1]/input',
        )
        end_date_elem = self.driver.find_element(
            By.XPATH,
            '//*[@id="content"]/div[2]/div/div[1]/form/div[2]/div/div[2]/input',
        )
        # Clear existing dates
        start_date_elem.clear()
        end_date_elem.clear()
        # set the dates
        start_date_elem.send_keys(self.start_date.strftime("%Y-%m-%d"))
        end_date_elem.send_keys(self.end_date.strftime("%Y-%m-%d"))
        print(
            "Date range set: {} to {}".format(
                self.start_date.strftime("%Y-%m-%d"), self.end_date.strftime("%Y-%m-%d")
            )
        )
        # 设置官员筛选
        speaker_elems = self.driver.find_elements(
            By.XPATH, '//*[@id="content"]/div[2]/div/div[1]/form/div[4]//div/label'
        )
        for speaker_elem in speaker_elems:
            speaker_elem.click()
            print("Selected speaker: {}".format(speaker_elem.text))

        # click the search button to filter the speeches
        search_button = self.driver.find_element(
            By.XPATH, '//*[@id="content"]/div[2]/div/div[1]/form/div[5]'
        )
        search_button.click()
        time.sleep(1.0)

        # 主循环获取所有演讲信息
        speech_infos_by_year = {}
        while True:
            # Get links from the current page
            speech_infos_by_year = self.get_speech_links_from_current_page(
                speech_infos_by_year
            )
            # Try to find and click the "Next" button
            try:
                next_button = self.driver.find_element(
                    By.CSS_SELECTOR, "li.pagination-next:not(.disabled) a"
                )
                self.driver.execute_script(
                    "arguments[0].click();", next_button
                )  # Wait for the next page to load
                continue
            except NoSuchElementException:
                print("Next button not found or disabled. Reached last page.")
                break

        speech_infos_by_year = sort_speeches_dict(speech_infos_by_year)
        self.speech_infos_by_year = speech_infos_by_year
        if self.save:
            json_update(self.speech_infos_filename, self.speech_infos_by_year)
        return speech_infos_by_year

    def split_position(self, applenation: str):
        # 识别出所有的职称
        position = [
            "Vice Chairman",
            "Vice Chair for Supervision",
            "Vice Chair",
            "Chair Pro Tempore",
            "Chairman",
            "Chair",
            "Governor",
        ]
        for p in position:
            if p in applenation:
                # 命中
                position = p.strip().title()
                speaker = applenation.replace(p, "").strip().title()
                return position, speaker
        return "Unknown", applenation

    def extract_single_speech(self, speech_info: dict):
        """提取单片演讲稿

        Args:
            speech_info (dict): _description_

        Returns:
            (dict): 新增content键表示演讲稿正文
        """
        try:
            self.driver.get(speech_info["href"])
            # 等待加载完
            WebDriverWait(self.driver, 10).until(
                EC.visibility_of_all_elements_located((By.ID, "content"))
            )
            time.sleep(1.0)

            # Extract the speech date
            # date = self.driver.find_element(By.CSS_SELECTOR, "#article > div.heading.col-xs-12.col-sm-8.col-md-8 > p.article__time").text
            # # Extract the speech title
            # title = self.driver.find_element(
            #     By.CSS_SELECTOR,
            #     "#article > div.heading.col-xs-12.col-sm-8.col-md-8 > h3",
            # ).text
            # Extract the speaker
            speaker = self.driver.find_element(
                By.CSS_SELECTOR,
                "#article > div.heading.col-xs-12.col-sm-8.col-md-8 > p.speaker",
            ).text
            # 提取出职位
            position, speaker = self.split_position(speaker)
            # Extract the speech content
            paragraph_elements = self.driver.find_elements(
                By.CSS_SELECTOR, "#article .col-xs-12.col-sm-8.col-md-8 > p"
            )

            if paragraph_elements:
                content = "\n\n".join([p.text.strip() for p in paragraph_elements])
                print(
                    "{} {} of {} {} content extracted.".format(
                        speech_info["date"], speech_info["title"], position, speaker
                    )
                )
            else:
                content = ""
                print(
                    "{} {} of {} {} content failed.".format(
                        speech_info["date"], speech_info["title"], position, speaker
                    )
                )
            speech = deepcopy(speech_info)
            speech.update(
                {
                    "position": position,
                    "speaker": speaker,
                }
            )
            speech.update({"content": content})

        except Exception as e:
            print(
                "Error when extracting speech content from {href}. {error}".format(
                    href=speech_info["href"], error=repr(e)
                )
            )
            speech = deepcopy(speech_info)
            speech.update(
                {
                    "position": "",
                    "speaker": "",
                }
            )
            speech.update({"content": ""})
            print(
                "{} {} {} content failed.".format(
                    speech_info["speaker"], speech_info["date"], speech_info["title"]
                )
            )

        return speech

    def extract_speeches(self, speech_infos_by_year: dict, start_date: str):
        """搜集每篇演讲的内容"""
        # 获取演讲的开始时间
        start_date = parse_datestring(start_date).date()
        start_year = start_date.year

        # 获取每年的演讲内容
        speeches_by_year = {}
        failed = []
        for year, single_year_infos in speech_infos_by_year.items():
            # 跳过之前的年份
            if int(year) < start_year:
                continue
            single_year_speeches = []
            for speech_info in single_year_infos:
                # 跳过start_date、end_date区间外的演讲
                if (
                    # 跳过已经存在的
                    parse_datestring(speech_info["date"]).date() < start_date
                ):
                    logger.info(
                        "Skip speech {date} {title} cause' it's earlier than start_date.".format(
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
                        "Extract {date} {title}".format(
                            date=speech_info["date"],
                            title=speech_info["title"],
                        )
                    )
                single_year_speeches.append(single_speech)
            single_year_speeches = sorted(
                single_year_speeches, key=lambda x: x["date"], reverse=True
            )
            speeches_by_year[year] = single_year_speeches
            if self.save:
                json_update(
                    self.SAVE_PATH + f"{self.__fed_name__}_speeches_{year}.json",
                    single_year_speeches,
                )
            print(f"Speeches of {year} collected.")
        # 保存演讲内容
        if self.save:
            speeches_by_year = sort_speeches_dict(speeches_by_year)
            # 保存读取失败的演讲内容
            json_dump(failed, self.failed_speech_infos_filename)
            # 更新已存储的演讲内容
            json_update(self.speeches_filename, speeches_by_year)
        return speeches_by_year

    def collect(self):
        """收集每篇演讲的信息

        Returns:
            _type_: _description_
        """
        # 提取每年演讲的基本信息（不含正文和highlights等）
        if os.path.exists(self.speech_infos_filename):
            # 加载已存在的演讲信息
            speech_infos = json_load(self.speech_infos_filename)
            # 获取当前页面上最新的演讲日期
            latest_speech_date = self.extract_lastest_speech_date()
            existed_speech_info_date = max(
                [
                    pd.to_datetime(speech_info["date"]).date()
                    for speech_info in speech_infos[max(speech_infos.keys())]
                ]
            )
            # 如果已存在的不是最新的，则获取; 否则无需获取.
            if latest_speech_date > existed_speech_info_date:
                speech_infos = self.extract_speech_infos()
        else:
            # 每次都搜集所有演讲的信息
            speech_infos = self.extract_speech_infos(
                start_date=existed_speech_info_date
            )  #
            if self.save:
                json_update(speech_infos, self.speech_infos_filename)

        # 查看已有的最新的演讲日期
        if os.path.exists(self.speeches_filename):
            # 按年整理的speeches
            existed_speeches = json_load(self.speeches_filename)
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

        # 提取演讲正文内容
        speeches = self.extract_speeches(speech_infos, existed_lastest)
        return speeches

    def extract_lastest_speech_date(self):
        """获取最近演讲的信息"""
        try:
            # 设置时间范围为最早和最晚
            from_years_element = self.driver.find_element(By.ID, "fromYears")
            from_years_options = [
                int(option.text)
                for option in Select(from_years_element).options
                if option.text.isdigit()
            ]
            from_years_element.send_keys(str(min(from_years_options)))

            to_years_element = self.driver.find_element(By.ID, "toYears")
            to_years_options = [
                int(option.text)
                for option in Select(to_years_element).options
                if option and option.text.isdigit()
            ]
            to_years_element.send_keys(str(max(to_years_options)))
            # 点击搜寻按键
            search_button = self.driver.find_element(
                By.CSS_SELECTOR, "button.btn.btn-link[aria-label='Submit Filters']"
            )
            search_button.click()
            # 等待页面
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located(
                    (By.XPATH, "//*[@id='content']/div[3]/div[1]/search-results/div")
                )
            )
            time.sleep(2.0)
        except Exception as e:
            print(f"Error setting date range: {e}")

        try:
            # 寻找最新一篇演讲的日期
            speech_items = self.drive.find_element(
                By.XPATH,
                "//*[@id='article']/div[1]/div[1]/div/time[@class and @datetime]",
            )
            latest_date = speech_items.get_attribute("datetime")
            return pd.to_datetime(latest_date).date()
        except Exception as e:
            print(f"Error extracting latest speech date: {e}")
            return None


def test_extract_speech_infos():
    """测试 extract_speeches 信息 方法"""
    scraper = BOGSpeechScraper()
    speech_infos = scraper.extract_speech_infos()
    print(speech_infos)


def test_extract_single_speech():
    """测试 extract_single_speech 方法"""
    scraper = BOGSpeechScraper()
    speech_info = {}

    speech = scraper.extract_single_speech(speech_info)
    print(speech)


def test():
    scraper = BOGSpeechScraper()
    scraper.collect()


def tran_speeches_records():
    old_speeches = json_load(
        "../../data/fed_speeches/bog_fed_speeches/bog_fed_speeches_old.json"
    )

    speeches_by_year = {}
    for speech in old_speeches:
        year = parse_datestring(speech["date"]).strftime("%Y")
        speeches_by_year.setdefault(year, []).append(speech)
    json_dump(
        speeches_by_year,
        "../../data/fed_speeches/bog_fed_speeches/bog_fed_speeches.json",
    )


def update_bog_speeches():
    start, end = 2024, 2025
    for year in range(start, end):
        print(year)
        filename = f"../../data/fed_speeches/bog_fed_speeches/bog_speeches_{year}.json"
        file = json_load(filename)
        json_update(
            "../../data/fed_speeches/bog_fed_speeches/bog_speeches.json",
            {f"{year}": file},
        )


if __name__ == "__main__":
    # test_extract_speech_infos()
    # test_extract_single_speech()
    # tran_speeches_records()
    # update_bog_speeches()
    test()
