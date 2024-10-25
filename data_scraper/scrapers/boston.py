#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
@File    :   boston.py
@Time    :   2024/10/24 16:47:09
@Author  :   wbzhang 
@Version :   1.0
@Desc    :   波士顿联储银行银行演讲稿数据爬取
'''


from datetime import datetime
import os
import re
import sys
import time

from utils.logger import get_logger
from utils.common import parse_datestring

sys.path.append("../../")
from scraper import SpeechScraper

from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.remote.webelement import WebElement
from utils.file_saver import json_dump, json_load, json_update

logger = get_logger('boston_speech_scraper')

class BostonSpeechScraper(SpeechScraper):
    URL = "https://www.bostonfed.org/news-and-events/speeches.aspx"
    __fed_name__ = "boston_fed"
    __name__ = f"{__fed_name__.title()}SpeechScraper"
    SAVE_PATH = f"../../data/fed_speeches/{__fed_name__}_fed_speeches/"

    def __init__(self, url: str = None, auto_save: bool = True):
        super().__init__(url)
        self.speech_infos_by_year = None
        self.speeches_by_year = None
        os.makedirs(self.SAVE_PATH, exist_ok=True)
        print(f"{self.SAVE_PATH} has been created.")
        self.save = auto_save

    def extract_speech_date(self, text: str):
        """提取段落中的日期

        Args:
            text (str): _description_

        Returns:
            _type_: _description_
        """
        # 正则分段
        try:
            date= ""
            paras = re.split(r"[\n\"·]+", text)
            for para in paras:
                parse_date = parse_datestring(para.split('|')[0].strip(' \n'))
                if isinstance(parse_date, datetime):
                    date = para
                else:
                    continue
            if date == "":
                print(paras[-1])
        except:
            date = ""
        return date
        

    def parse_single_row(self, data_row: WebElement):
        """解析Boston中的单个文章

        Args:
            data_row (_type_): _description_

        Returns:
            _type_: _description_
        """
        try:
            # 日期
            date_and_location = data_row.find_elements(
                By.CSS_SELECTOR,
                "p.date-and-location",
            )
            if date_and_location:
                date = date_and_location[0].text.split("|")[0].strip()
            else:
                date = self.extract_speech_date(data_row.text)
            # 标题
            title_element = data_row.find_elements(By.CSS_SELECTOR, "h1.card-title > a[href]")
            if title_element:
                title = title_element[0].text
                href = title_element[0].get_attribute("href")
            else:
                title = ""
                href = ""
            # 总结
            summaries = data_row.find_elements(By.CSS_SELECTOR, "p.event-text")
            summary = "\n\n".join(
                [p.text for p in summaries]  # .find_elements(By.TAG_NAME, "p")
            )
            # 作者
            speaker_paragraphs = data_row.find_elements(By.CSS_SELECTOR, "ul.speaker")
            speaker = "\n\n".join([p.text for p in speaker_paragraphs])

            speech_info = {
                "date": date,
                "title": title,
                "href": href,
                "summary": summary,
                "speaker": speaker,
            }
        except Exception as e:
            print(f"Parse Speech Info Error: {e}")
            # speech_info = None
            # TODO 提取失败依然返回，额外再处理
            speech_info = {
                "date": "",
                "title": "",
                "href": "",
                "summary": "",
                "speaker": "",
            }

        return speech_info

    def extract_speech_infos(self):
        """提取每篇演讲的链接、标题、日期和讲话人信息

        Returns:
            _type_: _description_
        """
        # 点击expanda all
        expand_all = self.driver.find_element(
            By.XPATH, "/html/body/main/div[1]/div[2]/div/div[1]/a[2]"
        )
        expand_all.click()
        # Wait for the content to load
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located(
                (By.XPATH, "/html/body/main/div[1]/div[2]/div/div[2]")
            )
        )

        panel_group = self.driver.find_element(
            By.XPATH, "/html/body/main/div[1]/div[2]/div/div[2]"
        )
        speeches_by_year = panel_group.find_elements(By.CLASS_NAME, "panel")
        speech_infos_by_year = {}
        counts = 0
        # 获取每一年的演讲
        for single_year_speeches in speeches_by_year:
            # 标题
            year = single_year_speeches.find_element(
                By.CSS_SELECTOR,
                "div.panel-heading > h4.panel-title > span.heading-title-text",
            ).text
            # 按数据行进行处理
            data_rows = single_year_speeches.find_elements(
                By.CSS_SELECTOR,
                "div.panel-collapse > div.panel-body > div.article-list-container > div.row",
            )
            data_rows
            speech_infos_single_year = []
            for data_row in data_rows:
                speech_info = self.parse_single_row(data_row)
                if speech_info and speech_info["href"].startswith(
                    "https://www.bostonfed.org/"
                ):
                    print(
                        "{date}. {title}. {speaker}\n".format(
                            date=speech_info["date"],
                            title=speech_info["title"],
                            speaker=speech_info["speaker"],
                        )
                    )
                    speech_infos_single_year.append(speech_info)
            print(
                "-" * 50
                + f"Speech Infos of {year} has been extracted."
                + "-" * 50
                + "\n"
            )
            speech_infos_by_year[year] = speech_infos_single_year
            counts += len(speech_infos_single_year)
        # 存储到类中
        self.speech_infos_by_year = speech_infos_by_year
        print(f"Extracted {counts} speeches from Boston Fed.")
        return speech_infos_by_year

    def extract_single_speech(self, speech_info: dict):
        try:
            href = speech_info["href"]
            self.driver.get(href)

            # Wait for the content to load
            WebDriverWait(self.driver, 10).until(
                EC.visibility_of_all_elements_located((By.ID, "main-content"))
            )
            time.sleep(1.2)

            # 演讲标题
            # speech_title = self.driver.find_element(
            #     By.CSS_SELECTOR,
            #     "#main-content > div.container.title-container > div > div > div > div > h1",
            # ).text
            speech_title = self.driver.find_element(
                By.XPATH,
                "//h1[contains(@class, 'title')]"
            ).text
            # 重点
            highlights_elements = self.driver.find_elements(
                By.CSS_SELECTOR,
                "#main-content > div:nth-child(9) > div > div > p",
            )
            if highlights_elements:
                highlights = "\n\n".join(
                    [highlight.text for highlight in highlights_elements]
                )
            else:
                highlights = ""
            # 内容
            content_elements = self.driver.find_element(
                By.CSS_SELECTOR,
                "#main-content > div.bodytextlist > div.container > div.row > div.col-sm-10.col-md-8.center-block > div.tag-box-container",
            )
            contents = content_elements.text
            speech = {
                "speech_title": speech_title,
                "highlights": highlights,
                "content": contents,
            }
        except:
            print(f"Error when extracting speech content from {href}")
            speech = {
                "speech_title": "",
                "highlights": "",
                "content": "",
            }
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
                if not speech_info["date"] or speech_info["date"] == "":
                    continue
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
            dates = []
            for speech_info in speech_infos[latest_year]:
                speech_date = parse_datestring(speech_info["date"])
                if isinstance(speech_date, datetime):
                    dates.append(speech_date)
            existed_lastest = max(dates).strftime("%b %d, %Y")
            # existed_lastest = "Jan 01, 2006"
            existed_lastest = "Jan 01, 2006"
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


def test_extract_speech_infos():
    """测试 extract_speeches 信息 方法"""
    scraper = BostonSpeechScraper()
    speech_infos = scraper.extract_speech_infos()
    print(speech_infos)


def test_extract_single_speech():
    """测试 extract_single_speech 方法"""
    scraper = BostonSpeechScraper()
    speech_info = {
        "year": "2024",
        "date": "2024-06-18",
        "title": "A Partnership for Progress",
        "href": "https://www.bostonfed.org/news-and-events/speeches/2024/a-partnership-for-progress.aspx",
        "summary": "Remarks to members of the Merrimack Valley community at the Lawrence Partnership’s 2024 Annual Meeting & 10th Year Anniversary celebration.",
        "speaker": "Susan M. Collins",
    }

    # speech_info = {
    #     "date": "November 17, 2023",
    #     "title": "Full Employment: A Broad-Based, Inclusive Goal",
    #     "href": "https://www.bostonfed.org/news-and-events/speeches/2023/full-employment-a-broad-based-inclusive-goal.aspx",
    #     "summary": "67th Economic Conference",
    #     "speaker": "Susan M. Collins, President & Chief Executive Officer",
    # }

    speech = scraper.extract_single_speech(speech_info)
    print(speech)


def test():
    scraper = BostonSpeechScraper()
    scraper.collect()


if __name__ == "__main__":
    # test_extract_speech_infos()
    # test_extract_single_speech()
    test()
