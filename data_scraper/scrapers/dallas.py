#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    :   dallas.py
@Time    :   2024/10/23 11:23:10
@Author  :   wbzhang
@Version :   1.0
@Desc    :   11K 达拉斯联储银行讲话数据爬取
"""

from copy import deepcopy
import os
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.remote.webelement import WebElement


from datetime import datetime

from data_scraper.scrapers.scraper import SpeechScraper
from utils.common import STANDRAD_DATE_FORMAT, get_latest_speech_date, parse_datestring
from utils.file_saver import json_dump, json_load, json_update, sort_speeches_dict, update_records
from utils.logger import logger

# 行长宣誓就职日期
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
        # 保存文件的文件名
        self.speech_infos_filename = (
            self.SAVE_PATH + f"{self.__fed_name__}_speech_infos.json"
        )
        self.speeches_filename = (
            self.SAVE_PATH + f"{self.__fed_name__}_speeches.json"
        )
        self.failed_speech_infos_filename = (
            self.SAVE_PATH + f"{self.__fed_name__}_failed_speech_infos.json"
        )

    def fetch_single_speech_info(self, speech_item: WebElement):
        """提取单个演讲元素的信息

        Args:
            speech_item (WebElement): 演讲元素
        """
        # 概要
        paras = re.split(r"[\n\"·]+", speech_item.text)
        # desc = paras[1].strip()
        # 日期
        date = ""
        for para in reversed(paras):
            parse_date = parse_datestring(para.split("·")[0].strip(" \n"), silent=True)
            if isinstance(parse_date, datetime):
                date = parse_date.strftime(STANDRAD_DATE_FORMAT)
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
            return "Unknown"

    def extract_speech_infos(self, existed_speech_infos: dict):
        """抽取演讲的信息"""
        self.driver.get(self.URL)
        # 搜寻每一个阶段的链接
        links = self.driver.find_elements(
            By.XPATH, "//*[@id='content']/div/div/ul/li/a[@href]"
        )
        links = {ele.text: ele.get_attribute("href") for ele in links}

        # 已经存储的日期.
        existed_speech_dates = set()
        for _, single_year_infos in existed_speech_infos.items():
            existed_speech_dates.update([info["date"] for info in single_year_infos])

        # 主循环获取所有演讲信息
        speech_infos_by_year = deepcopy(existed_speech_infos)
        for title, link in links.items():
            # 提取主席作为speaker
            speaker = self.extract_speaker_name(title)
            # 只抽取历任主席的讲话
            if "President" not in title:
                continue
            # 打开网站
            self.driver.get(link)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "dal-tabs"))
            )

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
                # 找到当前所有的演讲元素
                speech_items = self.driver.find_elements(
                    By.XPATH, "//*[@id='{}']/p".format(year)
                )
                for item in speech_items:
                    speech_info = self.fetch_single_speech_info(item)
                    speech_info ={"speaker": speaker, **speech_info}
                    # 如果日期已命中，则退出循环
                    if speech_info["date"] in existed_speech_dates:
                        break
                    # 从日期中获取年份
                    if speech_info["date"] != "":
                        true_year = str(parse_datestring(speech_info["date"]).year)
                    else:
                        true_year = year
                    # 仅保留在达拉斯任职时期的演讲
                    if speech_info["href"].startswith("https://www.dallasfed.org/"):
                        speech_infos_by_year.setdefault(true_year, []).append(
                            speech_info
                        )
                        print(
                            "{} | {} {} collected.".format(
                                speech_info["date"],
                                speech_info["speaker"],
                                speech_info["title"],
                            )
                        )
        if self.save:
            json_update(self.speech_infos_filename, speech_infos_by_year)
        return speech_infos_by_year

    def extract_single_speech(self, speech_info: dict):
        try:
            self.driver.get(speech_info["href"])
            # 等待加载完
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located((By.ID, "content"))
            )

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

            speech = {**speech_info, "content": content}
        except Exception as e:
            print(
                "Error when extracting speech content from {href}. {error}".format(
                    href=speech_info["href"], error=repr(e)
                )
            )
            speech = {**speech_info, "content": ""}
            print(
                "{} {} {} content failed.".format(
                    speech_info["speaker"], speech_info["date"], speech_info["title"]
                )
            )
        return speech

    def extract_speeches(
        self,
        speech_infos_by_year: dict,
        existed_speeches: dict,
        start_date: str = "Jan 01, 2006",
    ):
        """搜集每篇演讲的内容"""
        # 获取演讲的开始时间
        start_date = parse_datestring(start_date)
        start_year = start_date.year

        # 获取每年的演讲内容
        speeches_by_year = deepcopy(existed_speeches)
        failed = []
        for year, single_year_infos in speech_infos_by_year.items():
            if not year.isdigit():
                continue
            # 跳过之前的年份
            if int(year) < start_year:
                continue
            single_year_speeches = []
            _counts = 0
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
                print(
                    "{speaker} {date} | {title} extracted.".format(
                        speaker=speech_info["speaker"],
                        date=speech_info["date"],
                        title=speech_info["title"],
                    )
                )
                _counts +=1
            # 更新当年爬取内容
            speeches_by_year[year] = update_records(speeches_by_year[year], single_year_speeches)
            if self.save:
                json_update(
                    self.SAVE_PATH + f"{self.__fed_name__}_speeches_{year}.json",
                    single_year_speeches,
                )
            print(f"{_counts} speeches of {year} collected.")
        existed_speeches = sort_speeches_dict(speeches_by_year)
        # 保存演讲内容
        if self.save:
            # 保存读取失败的演讲内容
            json_dump(failed, self.failed_speech_infos_filename)
        if self.save and self.speeches_by_year!=existed_speeches:
            # 更新已存储的演讲内容
            json_update(self.speech_infos_filename, speeches_by_year)
        return speeches_by_year

    def collect(self):
        """收集每篇演讲的信息

        Returns:
            (dict): 收集到的演讲内容字典
        """
        # 提取每年演讲的基本信息（不含正文和highlights等）
        print(
            "==" * 20
            + f"Start collecting speech infos of {self.__fed_name__}"
            + "==" * 20
        )
        # 载入已存储的演讲信息
        if os.path.exists(self.speech_infos_filename):
            existed_speech_infos = json_load(self.speech_infos_filename)
        else:
            existed_speech_infos = {}
        speech_infos = self.extract_speech_infos(existed_speech_infos)

        # 提取已存储的演讲
        if os.path.exists(self.speeches_filename):
            existed_speeches = json_load(self.speeches_filename)
            # 查看已有的最新的演讲日期
            existed_lastest = get_latest_speech_date(existed_speeches)
        else:
            existed_speeches = {}
            existed_lastest = "Jan 01, 2006"

        # 提取演讲正文内容
        print(
            "==" * 20
            + f"Start extracting speech content of {self.__fed_name__} from {existed_lastest}"
            + "==" * 20
        )
        speeches = self.extract_speeches(
            speech_infos_by_year=speech_infos,
            existed_speeches=existed_speeches,
            start_date=existed_lastest,
        )
        print("==" * 20 + f"{self.__fed_name__} finished." + "==" * 20)
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
