#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
@File    :   minneapolis.py
@Time    :   2024/10/28 15:47:46
@Author  :   wbzhang 
@Version :   1.0
@Desc    :   明尼阿波利斯联储行长讲话数据
'''
from collections import OrderedDict
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

import time
from datetime import datetime

from data_scraper.scrapers.scraper import SpeechScraper
from utils.common import parse_datestring
from utils.file_saver import json_dump, json_load, json_update, records_update
from utils.logger import logger

today = datetime.today()


class MinneapolisSpeechScraper(SpeechScraper):
    URL = "https://www.minneapolisfed.org/publications-archive/all-speeches"
    __fed_name__ = "minneapolis"
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
        speech_infos_by_year = {}
        # 一直点击 Show Next 20 Items，直到不能点击
        while True:
            try:
                self.driver.find_element(By.ID, "js-fetch-content").click()
                time.sleep(0.2)
            except Exception as e:
                msg = "Click the next button, some error {} occured.".format(repr(e))
                print(msg)
                break
        # 搜集每个speech_info_items
        speech_info_items = self.driver.find_elements(
            By.XPATH, "//li[@class='i9-c-related-content__group--item']"
        )
        for speech_info_item in speech_info_items:
            # 标题&链接
            title = speech_info_item.find_element(By.XPATH, "./a[@href]").text
            href = speech_info_item.find_element(By.XPATH, "./a[@href]").get_attribute(
                "href"
            )
            # 日期
            date = speech_info_item.find_element(By.XPATH,
                                                 "./div/div").text
            date = date.replace("Speech on ", "").strip()
            # 年份
            year = date.split(',')[-1].strip()
            speech_infos_by_year.setdefault(year, []).append({
                "title": title,
                "href": href,
                "date": date
            })
            
        # 排个序
        speech_infos_by_year = OrderedDict(sorted(speech_infos_by_year.items()))
        self.speech_infos_by_year = speech_infos_by_year
        return speech_infos_by_year

    def extract_single_speech(self, speech_info: dict):
        speech = {"speaker": "", "position": "", "content": ""}
        try:
            self.driver.get(speech_info["href"])
            # 等待加载完
            WebDriverWait(self.driver, 10).until(
                EC.visibility_of_all_elements_located((By.TAG_NAME, "body"))
            )
            time.sleep(1.2)

            # 获取演讲者
            speaker = self.driver.find_element(
                By.XPATH,
                "//div[@class='i9-c-person-block--small__content--name']/a[@href]",
            ).text.strip()
            speech["speaker"] = speaker
            # 获取演讲者职位
            position = self.driver.find_element(
                By.XPATH,
                "//div[@class='i9-c-person-block--small__content--name']/small[@class='i9-c-person-block--small__content--position']",
            ).text.strip()
            speech["position"] = position
            # 查找是否包含youtube链接
            youtube_link_element = self.driver.find_elements(
                By.XPATH, "//div[(@id='i9-js-video-tabs--simple--UNIQUEPARENTID') or (@data-wf='video tabs')]"
            )
            # 如果包含youtube链接，则加上
            if youtube_link_element:
                youtube_link = youtube_link_element[0].find_element(
                    By.XPATH, ".//iframe[@id='videoFrame']"
                ).get_attribute("src")
                speech.setdefault("youtube_link", youtube_link.strip())

            # 查找所有正文元素
            options = [
                "//div[@class='i9-c-rich-text-area' and @data-wf='Rich Text Area']/p",
                "//div[@class='i9-c-rich-text-area' and @data-wf='Rich Text Area']",
            ]
            paragraph_elements = self.driver.find_elements(
                By.XPATH,
                "|".join(options),
            )
            if paragraph_elements:
                content = "\n\n".join(
                    [p.text.strip() for p in paragraph_elements]
                ).strip()
                print(
                    "{} {} {} content extracted.".format(
                        speech["speaker"],
                        speech_info["date"],
                        speech_info["title"],
                    )
                )
            else:
                content = ""
                print(
                    "{} {} {} content failed.".format(
                        speech["speaker"],
                        speech_info["date"],
                        speech_info["title"],
                    )
                )
            speech["content"] = content
        except Exception as e:
            print(
                "Error when extracting speech content from {href}. {error}".format(
                    href=speech_info["href"], error=repr(e)
                )
            )
            print(
                "{} {} {} content failed.".format(
                    speech["speaker"], speech_info["date"], speech_info["title"]
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
                if (
                    speech_info.get("date")
                    and parse_datestring(speech_info["date"]) <= start_date
                ):
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
                        "Extract {date} {title}".format(
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
            existed_lastest = "Mar. 30, 2023"
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
    scraper = MinneapolisSpeechScraper()
    speech_infos = scraper.extract_speech_infos()
    print(speech_infos)


def test_extract_single_speech():
    """测试 extract_single_speech 方法"""
    scraper = MinneapolisSpeechScraper()
    speech_info = {
    }

    speech = scraper.extract_single_speech(speech_info)
    print(speech)


def test():
    scraper = MinneapolisSpeechScraper()
    scraper.collect()


if __name__ == "__main__":
    # test_extract_speech_infos()
    # test_extract_single_speech()
    test()
