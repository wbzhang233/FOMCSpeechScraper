#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    :   new_york.py
@Time    :   2024/10/22 11:11:06
@Author  :   wbzhang
@Version :   1.0
@Desc    :   纽约联储讲话数据爬取
"""

import os
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select
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
from utils.logger import logger


class NewYorkSpeechScraper(SpeechScraper):
    URL = "https://www.newyorkfed.org/newsevents/speeches/index"
    __fed_name__ = "newyork"
    __name__ = f"{__fed_name__.title()}SpeechScraper"
    SAVE_PATH = f"../../data/fed_speeches/{__fed_name__}_fed_speeches/"

    def __init__(self, url: str = None, auto_save: bool = True):
        super().__init__(url)
        self.speech_infos_by_year = None
        self.speeches_by_year = None
        os.makedirs(self.SAVE_PATH, exist_ok=True)
        print(f"{self.SAVE_PATH} has been created.")
        self.save = auto_save

    def extract_speech_infos(self, last_names=None):
        """抽取演讲的信息"""
        speech_infos = {}
        try:
            self.driver.get(self.URL)
            # Wait for the table to be present
            table = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "newsTable"))
            )

            rows = table.find_elements(By.TAG_NAME, "tr")
            current_year = ""
            for row in rows:
                if row.text == "Speeches":
                    continue
                if "yrHead" in row.get_attribute("class"):
                    current_year = row.text.strip()
                    speech_infos[current_year] =  []
                    continue
                try:
                    columns = row.find_elements(By.TAG_NAME, "td")
                    if len(columns) < 2:
                        continue
                    # 获取日期
                    date_div = columns[0].find_element(By.TAG_NAME, "div")
                    date = (
                        date_div.text.strip().split("==")[0].strip()
                    )  # Extract date and remove any extra text
                    # 获取链接
                    link_elem = row.find_element(By.TAG_NAME, "a")
                    href = link_elem.get_attribute("href")
                    # Check if the speech is by one of the specified speakers
                    # 获取标题
                    title = link_elem.text.strip()
                    if last_names:
                        speaker_last_name = title.split(":")[0].strip()
                        if speaker_last_name in last_names:
                            speech_infos[current_year].append(
                                {"url": href, "date": date, "title": title}
                            )
                    else:
                        speech_infos[current_year].append(
                            {"url": href, "date": date, "title": title}
                        )
                except NoSuchElementException:
                    print(f"No speech link found in row: {row.text}")
                    continue

            print(f"Collected {len(speech_infos)} speech links.")
            return speech_infos
        except Exception as e:
            print(f"An error occurred while collecting speech links: {str(e)}")
            return speech_infos

    def fetch_speech_date(self):
        """提取NewYork联储演讲网站的演讲日期

        Returns:
            str: 演讲日期
        """
        try:
            date_elemment = self.driver.find_element(
                By.XPATH, "//body/div[@container_12]/div/div[@class='ts-contact-info']"
            )
            date_text = date_elemment.text.strip()
            posted_date = [line for line in date_text.split("\n") if "Posted" in line]
            date = posted_date[0] if posted_date else date_text.split("\n")[0]
        except Exception as e:
            print("{}".format(repr(e)))
            date = "Unknown"
        return date

    def fetch_speaker(self):
        """提取NewYork联储演讲网站的演讲人

        Returns:
            tuple(str, str): 演讲人和演讲人职位
        """
        try:
            speaker_elements = self.driver.find_elements(
                By.XPATH,
                "//div[@class='ts-contact-info']/a[@href]",
            )
            speaker = (
                speaker_elements[0].text.strip()
                if len(speaker_elements) > 0
                else "Unknown, UnKnown"
            )
            speaker = speaker.split(",", maxsplit=2)[0]
            officier_title = speaker.split(",", maxsplit=2)[1]
            # if not officier_title.startswith('President'):  # 非 Fed President
            #     return "NotPresident"
            return speaker, officier_title
        except Exception as e:
            print("{}".format(repr(e)))
            return "Unknown", "Unknown"

    def extract_single_speech(self, speech_info: dict):
        try:
            url = speech_info["url"]
            self.driver.get(url)
            title = self.driver.find_element(
                By.CLASS_NAME, "ts-article-title"
            ).text.strip()

            # Wait for the content to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "container_12"))
            )
            # Extract the "Posted" date
            # 日期
            date = self.fetch_speech_date()
            assert date != "Unknown", "Date was unknown"
            # 演讲人. 此处可能失败.
            speaker, officier_position = self.fetch_speaker()
            assert officier_position.startwith(
                "President"
            ), "The {} was not president but {}.".format(speaker, officier_position)
            # 演讲正文内容
            content_elem = self.driver.find_element(By.CLASS_NAME, "ts-article-text")
            paragraphs = content_elem.find_elements(By.TAG_NAME, "p")
            content = "\n\n".join([p.text for p in paragraphs if p.text.strip()])

            return {
                "title": title,
                "date": date,
                "speaker": speaker,
                "url": url,
                "content": content.strip(),
            }
        except TimeoutException as e:
            print(f"Timeout error extracting content from {url}: {str(e)}")
        except WebDriverException as e:
            print(f"WebDriver error extracting content from {url}: {str(e)}")
        except AssertionError as e:
            print(repr(e))
        except Exception as e:
            print(f"Unexpected error extracting content from {url}: {str(e)}")

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
            str: list[dict]
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

        soup = BeautifulSoup(self.driver.page_source, "html.parser")
        speech_items = soup.find_all("li", class_="result-item")
        # 提取最早的演讲的日期，锁定第一个演讲元素
        latest_date = (
            speech_items[0]
            .find("div", class_="date-reference")
            .text.split(" | ")[0]
            .strip()
        )
        return parse_datestring(latest_date)


def test_extract_speech_infos():
    """测试 extract_speeches 信息 方法"""
    scraper = NewYorkSpeechScraper()
    speech_infos = scraper.extract_speech_infos()
    print(speech_infos)


def test_extract_single_speech():
    """测试 extract_single_speech 方法"""
    scraper = NewYorkSpeechScraper()
    speech_info = {}

    speech = scraper.extract_single_speech(speech_info)
    print(speech)


def test():
    scraper = NewYorkSpeechScraper()
    scraper.collect()


if __name__ == "__main__":
    test_extract_speech_infos()
    # test_extract_single_speech()
    # test()
