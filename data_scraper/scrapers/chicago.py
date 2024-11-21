#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    :   chicago.py
@Time    :   2024/10/24 19:36:46
@Author  :   wbzhang
@Version :   1.0
@Desc    :   7G 芝加哥联储行长讲话爬取
"""

from collections import OrderedDict
import os
import re
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import time
from datetime import datetime

from data_scraper.scrapers.scraper import SpeechScraper
from utils.common import parse_datestring
from utils.file_saver import json_dump, json_load, json_update, update_records
from utils.logger import get_logger

today = datetime.today()


class ChicagoSpeechScraper(SpeechScraper):
    URL = "https://www.chicagofed.org/people/chicago-fed-presidents"
    __fed_name__ = "chicago"
    __name__ = f"{__fed_name__.title()}SpeechScraper"
    SAVE_PATH = f"../../data/fed_speeches/{__fed_name__}_fed_speeches/"

    logger = get_logger(
        logger_name=f"{__fed_name__}_speech_scraper", log_filepath="../../log/"
    )

    def __init__(self, url: str = None, auto_save: bool = True, **kwargs):
        super().__init__(url)
        self.speech_infos_by_year = None
        self.speeches_by_year = None
        os.makedirs(self.SAVE_PATH, exist_ok=True)
        print(f"{self.SAVE_PATH} has been created.")
        self.save = auto_save

    def extract_speaker_name(self, text: str):
        """正则匹配演讲人姓名

        Args:
            text (str): _description_

        Returns:
            _type_: _description_
        """
        pattern = r"President\s+(.*?)(?=\()"

        match = re.search(pattern, text)
        if match:
            result = match.group(1)
            return result.strip()
        else:
            return "Unknown"

    def extract_speech_date(self, speech: dict):
        try:
            # 年份
            year = speech["href"].split('/')[-2]
            # 最后的划分日期
            title = speech["href"].split("/")[-1]
            month, date = title.split("-")[0], title.split("-")[1]
            # 转为日期
            if month.isdigit():
                # print(f"{year}-{month}-{date}")
                speech_date = pd.to_datetime(f"{year}-{month}-{date}")
            else:
                # print(f"{month}. {date}, {year}")
                speech_date = pd.to_datetime(f"{month}. {date}, {year}")
            # 若记录日期为空、或者年份与识别日期年份不一致，则更新日期
            # print(
            #     "{} is going to be replace by {}".format(
            #         speech["date"], speech_date.date().strftime(format="%B %d, %Y")
            #     )
            # )
            return speech_date.strftime("%B %d, %Y")  # speech["date"] =
        except Exception as e:
            msg = "Error  {} occured when processing {}.".format(repr(e), speech["href"])
            print(msg)
            self.logger.info(msg=msg)
            return None

    def extract_president_speech_infos(self, president_info: dict):
        """提取芝加哥联储某位行长的演讲信息

        Args:
            president_info (dict): _description_
        """
        href = president_info["href"]
        self.driver.get(href)
        time.sleep(1.0)
        WebDriverWait(self.driver, 10).until(
            EC.visibility_of_all_elements_located((By.TAG_NAME, "body"))
        )
        speech_infos = {}
        # 如果是Goolsbee，分流
        if president_info["name"].endswith("Goolsbee"):
            # 点击 Speaking Engagements
            click_speaking_engagement = self.driver.find_element(
                By.XPATH, "//a[@href and text()='Speaking Engagements']"
            )
            click_speaking_engagement.click()
            time.sleep(1.2)
            # 找到所有的演讲元素
            speech_items = self.driver.find_elements(
                By.XPATH, "//div[@class='cyan-publication']"
            )
            # 搜集所有资料
            for item in speech_items:
                title = item.find_element(By.XPATH, "./a[@href]").text.strip()
                href = item.find_element(By.XPATH, "./a[@href]").get_attribute("href")
                # 获取日期
                date = item.find_element(
                    By.XPATH, "./p[@class='cyan-publication-date']"
                ).text.strip()
                summary = item.text.split("\n")[-1].strip()
                # 按年收纳
                year = str(parse_datestring(date).year)
                speech_infos.setdefault(year, []).append(
                    {
                        "speaker": president_info["name"],
                        "title": title,
                        "href": href,
                        "date": date,
                        "summary": summary,
                    }
                )
        else:
            # 点击 Speeches
            click_speeches = self.driver.find_element(By.XPATH, "//label[@for='tab7']")
            click_speeches.click()
            time.sleep(1.2)
            speech_items = self.driver.find_elements(
                By.XPATH,
                "//section[@id='speeches']/div[@class='peoplePublication__container']",
            )
            for item in speech_items:
                title = item.find_element(By.XPATH, "./div/a[@href]").text.strip()
                href = item.find_element(By.XPATH, "./div/a[@href]").get_attribute(
                    "href"
                )
                # 根据href来解析日期
                date = self.extract_speech_date({"href": href})
                p_items = item.find_elements(By.TAG_NAME, "p")
                summary = "\n\n".join([p.text for p in p_items]).strip()
                # 查找上一个h3元素
                year = item.find_element(By.XPATH, "./preceding-sibling::h3[1]").text
                speech_infos.setdefault(year, []).append(
                    {
                        "speaker": president_info["name"],
                        "title": title,
                        "href": href,
                        "date": date,
                        "summary": summary,
                    }
                )

        return speech_infos

    def extract_speech_infos(self):
        """抽取演讲的信息"""
        # 搜寻历任每一任主席的资料
        president_elements = self.driver.find_elements(
            By.XPATH,
            "//table[@class='focus-people']/tbody/tr/td[contains(@style, '!important;')]",
        )
        president_infos = []
        for element in president_elements:
            # 名字
            name = element.find_element(By.XPATH, "./a[@title]").text
            # 链接
            href = element.find_element(By.XPATH, "./a[@title]").get_attribute("href")
            paras = element.text.split("\n")
            # 任期
            start_year = paras[-1].split(" – ")[0].strip()
            last_year = paras[-1].split(" – ")[-1].strip()
            last_year = str(today.year) if last_year == "present" else last_year
            # 名讳
            order = paras[-2]
            president_infos.append(
                {
                    "name": name,
                    "href": href,
                    "order": order,
                    "start_year": start_year,
                    "last_year": last_year,
                }
            )

        # 主循环获取所有演讲信息
        speech_infos_by_year = {}
        for president_info in president_infos:
            # 太早的不要
            if int(president_info["start_year"]) < 1994:
                continue
            # 主席名称
            # speaker = president_info['name']
            infos = self.extract_president_speech_infos(president_info)
            for year, new_speech_infos in infos.items():
                if year in speech_infos_by_year:
                    speech_infos_by_year[year] = update_records(
                        speech_infos_by_year[year],
                        new_speech_infos,
                        tag_fields=["speaker", "title"],
                    )
                else:
                    speech_infos_by_year[year] = new_speech_infos
                msg = "{number} speech infos of {year} was collected.".format(
                    number=len(speech_infos_by_year[year]), year=year
                )
                print(msg)
                self.logger.info(msg=msg)
        # 排个序
        speech_infos_by_year = OrderedDict(sorted(speech_infos_by_year.items()))
        msg = "-" * 50 + "All speech infos was collected." + "-" * 50
        print(msg)
        self.logger.info(msg=msg)
        self.speech_infos_by_year = speech_infos_by_year
        return speech_infos_by_year

    def extract_single_speech(self, speech_info: dict):
        try:
            self.driver.get(speech_info["href"])
            # 等待加载完
            WebDriverWait(self.driver, 10).until(
                EC.visibility_of_all_elements_located((By.TAG_NAME, "body"))
            )
            time.sleep(1.2)

            # last updated date
            last_updated_elements = self.driver.find_elements(
                By.CLASS_NAME, "cfedDetail__lastUpdated"
            )
            if last_updated_elements:
                last_updated = last_updated_elements[0].text.split(":")[1].strip()
                last_updated = parse_datestring(last_updated).strftime("%B %d, %Y")
                speech_info["date"] = last_updated
            else:
                speech_info.setdefault("date", "")

            # 查找所有元素
            options = [
                "//div[@class='cfedContent']//p",
                "//div[@class='event__intro']/p",
                "//div[@class='cfedCotent__text']//p",
                "//div[@class='cfedCotent__text']/p",
                "//div[@class='cfedCotent__text']/div/p",
            ]
            paragraph_elements = self.driver.find_elements(
                By.XPATH,
                "|".join(options),
            )

            if paragraph_elements:
                content = "\n\n".join(
                    [p.text.strip() for p in paragraph_elements]
                ).strip()
                msg = "{} {} {} content extracted.".format(
                    speech_info["speaker"],
                    speech_info["date"],
                    speech_info["title"],
                )
            else:
                content = ""
                msg = "{} {} {} content failed.".format(
                    speech_info["speaker"],
                    speech_info["date"],
                    speech_info["title"],
                )
            print(msg)
            self.logger.info(msg=msg)

            speech = {"content": content}
        except Exception as e:
            msg = "Error when extracting speech content from {href}. {error}".format(
                href=speech_info["href"], error=repr(e)
            )
            print(msg)
            self.logger.info(msg)
            speech = {"content": ""}
            msg = "{} {} {} content failed.".format(
                speech_info["speaker"], speech_info["date"], speech_info["title"]
            )
            print(msg)
            self.logger.info(msg)
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
                    self.logger.info(
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
                    self.logger.warning(
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
        # if os.path.exists(self.SAVE_PATH + f"{self.__fed_name__}_speech_infos.json"):
        #     speech_infos = json_load(
        #         self.SAVE_PATH + f"{self.__fed_name__}_speech_infos.json"
        #     )
        #     # 查看已有的最新的演讲日期
        #     latest_year = max([k for k, _ in speech_infos.items()])
        #     existed_lastest = max(
        #         [
        #             parse_datestring(speech_info["date"])
        #             for speech_info in speech_infos[latest_year]
        #         ]
        #     ).strftime("%b %d, %Y")
        #     self.logger.info("Speech Infos Data already exists, skip collecting infos.")
        #     existed_lastest = "Jan 01, 2024"
        # else:
        speech_infos = self.extract_speech_infos()
        if self.save:
            json_dump(
                speech_infos,
                self.SAVE_PATH + f"{self.__fed_name__}_speech_infos.json",
            )
        existed_lastest = "Oct 17, 2024"

        # 提取演讲正文内容
        speeches = self.extract_speeches(speech_infos, existed_lastest)
        return speeches


def test_extract_speech_infos():
    """测试 extract_speeches 信息 方法"""
    scraper = ChicagoSpeechScraper()
    speech_infos = scraper.extract_speech_infos()
    print(speech_infos)


def test_extract_single_speech():
    """测试 extract_single_speech 方法"""
    scraper = ChicagoSpeechScraper()
    speech_info = {
        "date": "August 21, 2018",
        "title": "Where We Stand: Assessment of Economic Conditions and Implications for Monetary Policy",
        "href": "https://www.dallasfed.org/news/speeches/kaplan/2018/rsk180821.aspx",
        "speaker": "Robert S. Kaplan",
    }

    speech = scraper.extract_single_speech(speech_info)
    print(speech)


def test():
    scraper = ChicagoSpeechScraper()
    scraper.collect()


if __name__ == "__main__":
    # test_extract_speech_infos()
    # test_extract_single_speech()
    test()
