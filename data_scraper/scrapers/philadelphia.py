#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    :   philadelphia.py
@Time    :   2024/10/23 11:23:10
@Author  :   wbzhang
@Version :   1.0
@Desc    :   费城联储银行讲话数据爬取
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


class PhiladelphiaSpeechScraper(SpeechScraper):
    URL = "https://www.philadelphiafed.org/search-results?searchtype=speeches"
    __fed_name__ = "philadelphia"
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
        # 设置为 Most recent
        sory_by_button = self.driver.find_element(
            By.XPATH,
            "//*[@id='content']/section[1]/div/div/div[@class='search-sort']/ul/li[.='Most Recent']/button",
        )
        sory_by_button.click()
        time.sleep(1.2)

        # 主循环获取所有演讲信息
        speech_infos_by_year = {}
        while True:
            # 获取当前网页上所有演讲元素. 依次解析每一条
            speech_items = self.driver.find_elements(
                By.XPATH,
                "//*[@id='content']/section[1]/div/section/div/div[@class='result search-result']",
            )

            for i, item in enumerate(speech_items):
                # 话题类型记录一下
                date_topic = speech_items[i].get_attribute("data-topic")
                # 提取日期
                date = speech_items[i].find_element(
                    By.XPATH,
                    "header/div[@class='result-authors']/p[@class='result-date']",
                )
                date = date.text.strip()
                if len(date.split(",")) >= 2:
                    year = int(date.split(",")[1].strip(" ")) 
                else:
                    continue
                    year = min(speech_infos_by_year.keys())
                if year not in speech_infos_by_year:
                    speech_infos_by_year[year] = []
                date = parse_datestring(date).strftime("%B %d, %Y")
                # 提取演讲者
                speaker = speech_items[i].find_element(
                    By.XPATH, "header/div/ul[@class='authors']/li[@class='author']/a[@href]"
                ).text.strip()

                # 提取标题和链接
                title_link = item.find_element(
                    By.XPATH, "header/h2[@class='result-title']/a[@href]"
                )
                title = title_link.text.strip()
                href = title_link.get_attribute("href")

                speech_infos_by_year[year].append(
                    {
                        "date": date,
                        "speaker": speaker,
                        "title": title,
                        "href": href,
                        "date_topic": date_topic,
                    }
                )

            # 点击下一页
            try:
                next_button = self.driver.find_element(
                    By.XPATH,
                    "//*[@id='content']/section[1]/div/section/ul/li[@class='next']/a[@role='button']",
                )
                self.driver.execute_script("arguments[0].click();", next_button)
                # 等待页面加载
                time.sleep(1.2)
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

            # 演讲人职位
            author_title = self.driver.find_element(
                by=By.XPATH,
                value="//*[@id='content']/div[1]/div[2]/div/div[@class='author-desc']/p[@class='author-title']",
            )
            position = author_title.text.strip() if author_title else ""

            # 主内容元素
            main_content = self.driver.find_element(By.ID, "content")
            paragraph_elements = main_content.find_elements(
                By.XPATH,
                "//div[contains(@class, 'article-body')]/p",
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

            speech = {"content": content, "position": position}
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

    def update(self):
        """更新报告

        Returns:
            _type_: _description_
        """
        # 读取本地演讲信息
        speech_infos = json_load(
            self.SAVE_PATH + f"{self.__fed_name__}_speech_infos.json"
        )
        # 查看最新的演讲日期
        latest_year = max([k for k, _ in speech_infos.items()])
        existed_lastest = max(
            [
                parse_datestring(speech_info["date"])
                for speech_info in speech_infos[latest_year]
            ]
        )
        # 获取网页上最新的报告日期
        latest_speech_date = self.extract_lastest_speech_date()
        return latest_speech_date > existed_lastest


def test_extract_speech_infos():
    """测试 extract_speeches 信息 方法"""
    scraper = PhiladelphiaSpeechScraper()
    speech_infos = scraper.extract_speech_infos()
    print(speech_infos)


def test_extract_single_speech():
    """测试 extract_single_speech 方法"""
    scraper = PhiladelphiaSpeechScraper()
    speech_info = {
        "date": "February 24, 2020",
        "speaker": "Loretta J. Mester",
        "title": "The Outlook for the Economy and Monetary Policy in 2020",
        "href": "https://www.clevelandfed.org/collections/speeches/sp-20200224-outlook-for-the-economy-and-monetary-policy-in-2020",
        "highlights": "Speech by Loretta J. Mester, President and Chief Executive Officer, Federal Reserve Bank of Cleveland - The Outlook for the Economy and Monetary Policy in 2020 - 36th Annual NABE Economic Policy Conference - Washington, DC - February 24, 2020",
    }

    speech = scraper.extract_single_speech(speech_info)
    print(speech)


def test():
    scraper = PhiladelphiaSpeechScraper()
    scraper.collect()


if __name__ == "__main__":
    # test_extract_speech_infos()
    # test_extract_single_speech()
    test()
