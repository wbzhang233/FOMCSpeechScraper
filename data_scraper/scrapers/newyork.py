#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    :   new_york.py
@Time    :   2024/10/22 11:11:06
@Author  :   wbzhang
@Version :   1.0
@Desc    :   2B 纽约联储讲话数据爬取
"""

import os
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
)

from data_scraper.scrapers.scraper import SpeechScraper
from utils.common import parse_datestring
from utils.file_saver import json_dump, json_load, json_update, sort_speeches_records
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

    def extract_speech_infos(self, mode: str = "history", last_names=None):
        """抽取演讲的信息"""
        speech_infos = {}
        try:
            self.driver.get(self.URL)
            # Wait for the table to be present
            table = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "newsTable"))
            )

            # 直接找到所有行元素，然后遍历每一行.
            row = table.find_element(
                By.XPATH,
                "/html/body/div[1]/div[2]/table/tbody/tr[contains(@class, 'yrHead')]",
            )
            latest_year = row.text.strip()
            current_year = row.text.strip()
            while row:
                try:
                    if row.text == "Speeches":
                        row = row.find_element(By.XPATH, "following-sibling::tr")
                        continue
                    # 更新年份
                    if "yrHead" in row.get_attribute("class"):
                        current_year = row.text.strip()
                        speech_infos[current_year] = []
                        row = row.find_element(By.XPATH, "following-sibling::tr")
                        continue
                    # 如果mode为update，则仅获取最新一年的信息.
                    if mode == "update" and current_year != latest_year:
                        break
                    # 如果只有一列，则跳过.
                    columns = row.find_elements(By.TAG_NAME, "td")
                    if len(columns) < 2:
                        row = row.find_element(By.XPATH, "following-sibling::tr")
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
                                {
                                    "date": date,
                                    "title": title,
                                    "url": href,
                                }
                            )
                    else:
                        speech_infos[current_year].append(
                            {
                                "date": date,
                                "title": title,
                                "url": href,
                            }
                        )
                    row = row.find_element(By.XPATH, "following-sibling::tr")
                except NoSuchElementException:
                    print(f"No speech link found in row: {row.text}")
                    break
                except Exception as e:
                    msg = f"Error {repr(e)} occured when extracting speech links."
                    print(msg)
                    break

            print(f"Collected {len(speech_infos)} speech links.")
        except Exception as e:
            print(f"An error occurred while collecting speech links: {str(e)}")
        # 自动保存
        if self.save:
            json_update(self.speech_infos_filename, speech_infos)
        return speech_infos

    def fetch_speech_date(self):
        """提取NewYork联储演讲网站的演讲日期

        Returns:
            str: 演讲日期
        """
        try:
            date_elemment = self.driver.find_element(
                By.XPATH, "/html/body/div[@container_12]/div/div[@class='ts-contact-info']"
            )
            date_text = date_elemment.text.strip()
            posted_date = [line for line in date_text.split("\n") if "Posted" in line]
            date = posted_date[0] if posted_date else date_text.split("\n")[0]
        except Exception as e:
            print("{}".format(repr(e)))
            date = ""
        return date

    def fetch_speaker(self):
        """提取NewYork联储演讲网站的演讲人

        Returns:
            tuple(str, str): 演讲人和演讲人职位
        """
        try:
            speaker_elements = self.driver.find_elements(
                By.XPATH,
                "/html/body/div/div/div[@class='ts-contact-info'][2]",
            )
            speaker = (
                speaker_elements[0].text.strip() if len(speaker_elements) > 0 else " , "
            )
            splits = speaker.split(",", maxsplit=2)
            if len(splits) < 2:
                speaker = speaker[0]
                position = ""
            else:
                speaker = splits[0].strip()
                position = splits[1].strip()
            return speaker, position
        except Exception as e:
            print("{}".format(repr(e)))
            return "", ""

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
            # 日期
            date = self.fetch_speech_date()
            speaker, officier_position = self.fetch_speaker()
            # 演讲正文内容
            content_elem = self.driver.find_element(By.CLASS_NAME, "ts-article-text")
            paragraphs = content_elem.find_elements(By.TAG_NAME, "p")
            content = "\n\n".join([p.text for p in paragraphs if p.text.strip()])

            return {
                "speaker": speaker,
                "position": officier_position,
                "date": date if date else speech_info["date"],
                "title": title,  # 演讲主题
                "url": url,
                "content": content.strip(),
            }
        except Exception as e:
            print(f"Unexpected error extracting content from {url}: {str(e)}")
            return {
                "speaker": speaker,
                "position": "",
                **speech_info,
                "content": "",
            }

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
                if single_speech["position"].startswith("President"):
                    single_year_speeches.append(single_speech)
            # 排序
            single_year_speeches = sort_speeches_records(single_year_speeches)
            speeches_by_year[year] = single_year_speeches
            # 存储每年的报告
            if self.save:
                json_update(
                    self.SAVE_PATH + f"{self.__fed_name__}_speeches_{year}.json",
                    single_year_speeches,
                )
            print(f"Speeches of {year} collected.")
        # 保存演讲内容
        if self.save:
            # 保存读取失败的演讲内容
            json_dump(failed, self.failed_speech_infos_filename)
            # 更新已存储的演讲内容
            json_update(self.speeches_filename, speeches_by_year)
        return speeches_by_year

    def collect(self, mode: str = "update"):
        """收集每篇演讲的信息

        Returns:
            str: list[dict]
        """
        print(
            "==" * 20
            + f"Start collecting speech infos of {self.__fed_name__}"
            + "==" * 20
        )
        # 提取每年演讲的基本信息（不含正文和highlights等）
        speech_infos = self.extract_speech_infos(mode=mode)
        # 提取已存储的演讲
        if os.path.exists(self.speeches_filename):
            existed_speeches = json_load(self.speeches_filename)
            # 查看已有的最新的演讲日期
            latest_year = max([k for k, _ in existed_speeches.items()])
            existed_lastest = max(
                [
                    parse_datestring(speech["date"])
                    for speech in existed_speeches[latest_year]
                ]
            ).strftime("%b %d, %Y")
        else:
            existed_lastest = "Jan 01, 2006"

        # 提取演讲正文内容
        print(
            "==" * 20
            + f"Start extracting speech content of {self.__fed_name__} from {existed_lastest}"
            + "==" * 20
        )
        speeches = self.extract_speeches(speech_infos, existed_lastest)
        print("==" * 20 + f"{self.__fed_name__} finished." + "==" * 20)
        return speeches


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
    # test_extract_speech_infos()
    # test_extract_single_speech()
    test()
