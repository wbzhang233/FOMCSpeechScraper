#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    :   richmond.py
@Time    :   2024/09/27 18:26:36
@Author  :   wbzhang
@Version :   1.0
@Desc    :   5E 里奇蒙德联储行长讲话数据爬取
"""

from copy import deepcopy
import os
import sys
import time

from utils.common import get_latest_speech_date, parse_datestring

sys.path.append("../../")
from scraper import SpeechScraper
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.remote.webelement import WebElement
from utils.file_saver import json_dump, json_load, json_update, sort_speeches_dict

PROMPT = """
下面这个链接是Richmond联储官员讲话的网址。
https://www.richmondfed.org/press_room/speeches

我想要从上面网址中使用Python和Selenium来爬取每一条speech数据，包括日期、标题、speech链接、作者和摘要,
注意：这个网站是按年来收集每一条speech数据，因此需要点击年份控件将每年的内容展开。
请帮我开发代码爬取所有数据
"""


class RichmondSpeechScraper(SpeechScraper):
    URL = "https://www.richmondfed.org/press_room/speeches"  # ?mode=archive#2
    SAVE_PATH = "../../data/fed_speeches/richmond_fed_speeches/"
    __fed_name__ = "richmond"

    def __init__(self, url: str = None, auto_save: bool = True):
        super().__init__(url)
        self.speech_infos_by_year = None
        self.speeches_by_year = None
        os.makedirs(self.SAVE_PATH, exist_ok=True)
        self.save = auto_save
        # 保存文件的文件名
        self.speech_infos_filename = (
            self.SAVE_PATH + f"{self.__fed_name__}_speech_infos.json"
        )
        self.speeches_filename = self.SAVE_PATH + f"{self.__fed_name__}_speeches.json"
        self.failed_speech_infos_filename = (
            self.SAVE_PATH + f"{self.__fed_name__}_failed_speech_infos.json"
        )

    def expand_all(self, accordian: WebElement):
        """展开所有年份

        Args:
            accordian (_type_): _description_
        """
        year_links = accordian.find_elements(By.CSS_SELECTOR, "li a[data-anchor-id]")
        for i, link in enumerate(year_links):
            try:
                link.click()
                # 等待加载完
                time.sleep(1.0)
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located(
                        (
                            By.CSS_SELECTOR,
                            f"# pi_center_column > div.component.comp-archive > ul > li:nth-child({i}) > div.content[data-target-id]",
                        )
                    )
                )
            except Exception as e:
                print(repr(e))

    def click_years(self):
        """逐个点击所有年份标题展开"""
        title_element = self.driver.find_element(
            By.XPATH,
            "//div[contains(@class,'component')]/ul[@class='accordion']/li",  # //a[starts-with(@href, 'javascript:;')]
        )

        while title_element:
            try:
                # 获取标题，太早的不点击
                year_title = title_element.find_element(
                    By.CSS_SELECTOR, "a[href]"
                ).text.strip()
                year_str = year_title[0:4]
                if year_str.isdigit() and int(year_str) < 2024:
                    break
                # 如果内容区域没有展开，则点击标题
                title_element.click()
                # 等待内容区域展开
                time.sleep(1.0)
            except Exception as e:
                print(
                    f"Error when clicking year {title_element.text.strip()}. {repr(e)}"
                )
                pass
            # 寻找下一个按键
            following_siblings = title_element.find_elements(
                By.XPATH, "following-sibling::li[1]"
            )
            if len(following_siblings) == 0:
                break
            else:
                title_element = following_siblings[0]
        print("==" * 20 + "All years title was expanded." + "==" * 20)

    def pre_setting(self):
        # 点击view more
        view_more = self.driver.find_element(
            By.XPATH, "//*[@id='pi_center_column']/div[2]/a"
        )
        view_more.click()
        # Wait for the content to load
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "content"))
        )
        # 展开所有年份的按键
        accordian = self.driver.find_element(
            By.XPATH,
            "/html/body/div[1]/main/div/div/div/div[2]/div[2]/div[1]/ul",
        )
        # option 1:
        self.click_years()
        return accordian

    def extract_speech_infos(self, existed_speech_infos:dict):
        """抽取演讲的基本信息

        Returns:
            dict: 按年整理的基本信息
        """
        # 预先点击控件，并返回accordian元素
        accordian = self.pre_setting()
        # 已经存储的日期.
        existed_speech_dates = set()
        for _, single_year_infos in existed_speech_infos.items():
            existed_speech_dates.update([info["date"] for info in single_year_infos])

        speeches_by_year = accordian.find_elements(By.TAG_NAME, "li")
        speech_infos_by_year = deepcopy(existed_speech_infos)
        # 获取每一年的演讲
        for single_year_speeches in speeches_by_year:
            # 标题
            year_title = single_year_speeches.find_element(
                By.CSS_SELECTOR, "a[href]"
            ).text
            year = year_title.split("\n")[0]
            # 按数据行进行处理
            data_row = single_year_speeches.find_element(
                By.CSS_SELECTOR, "div.content > div.data__row"
            )
            speech_infos_single_year = []
            while data_row:
                # 日期
                date = data_row.find_element(
                    By.CSS_SELECTOR,
                    "section > div.data__pub-container > span.data__date",
                ).text
                # 若已存在，则跳出循环
                if parse_datestring(date) in existed_speech_dates:
                    break
                # 标题
                title_element = data_row.find_element(
                    By.CSS_SELECTOR, "section.data__group > div.data__title"
                )
                title = title_element.text
                href = title_element.find_element(By.TAG_NAME, "a").get_attribute(
                    "href"
                )
                # 总结
                summaries = data_row.find_elements(
                    By.CSS_SELECTOR, "section > div.data__summary > p"
                )
                summary = "\n\n".join(
                    [p.text for p in summaries]  # .find_elements(By.TAG_NAME, "p")
                )
                # 作者
                speaker_paragraphs = data_row.find_elements(
                    By.CSS_SELECTOR, "section.data__group > div.data__authors > p"
                )
                speaker = "\n\n".join([p.text for p in speaker_paragraphs])

                speech_info = {
                    "speaker": speaker,
                    "year": year,
                    "date": date,
                    "title": title,
                    "summary": summary,
                    "href": href,
                }
                speech_infos_single_year.append(speech_info)
                # 寻找下一个兄弟节点的 data_row
                next_siblings = data_row.find_elements(
                    By.XPATH, "./following-sibling::div[contains(@class, 'data__row')]"
                )
                if len(next_siblings) == 0:
                    break
                else:
                    data_row = next_siblings[0]
            speech_infos_by_year[year] = speech_infos_single_year
        # 排序并去重
        speech_infos_by_year = sort_speeches_dict(
            speech_infos_by_year,
            sort_filed="date",
            required_keys=["date", "title", "href"],
            tag_fields=["date", "href"],
        )
        if self.save:
            json_update(self.speech_infos_filename, speech_infos_by_year)
        return speech_infos_by_year

    def extract_single_speech(self, speech_info: dict):
        """获取单篇演讲的内容

        Args:
            speech_info (_type_): _description_

        Returns:
            dict: 单篇演讲稿内容
        """
        try:
            href = speech_info["href"]
            self.driver.get(href)
            # Wait for the content to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "tmplt.speech"))
            )

            # 重点
            highlights_elements = self.driver.find_elements(
                By.CSS_SELECTOR,
                "#pi_center_column > div.tmplt.speech > div.component.comp-highlights > ul > li",
            )
            highlights = "\n\n".join(
                [highlight.text for highlight in highlights_elements]
            )
            # 内容
            content = self.driver.find_element(
                By.CSS_SELECTOR,
                "#pi_center_column > div.tmplt.speech > div.tmplt__content",
            )
            content_elements = content.find_elements(By.TAG_NAME, "p")
            contents = "\n\n".join([p.text for p in content_elements])
            speech = {
                **speech_info,
                "highlights": highlights,
                "content": contents,
            }
        except Exception as e:
            print(f"Error when extracting speech content from {href}. Error: {e}")
            speech = {
                **speech_info,
                "highlights": "",
                "content": "",
            }
        return speech

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
                    singe_year_speeches,
                )
        if self.save:
            json_dump(failed, self.failed_speech_infos_filename)
        return speeches_by_year

    def collect(self):
        """演讲内容收集

        Returns:
            dict: 按年整理的演讲稿字典
        """
        # 提取每年演讲的基本信息（不含正文和highlights等）
        print(
            "==" * 20
            + f"Start collecting speech infos of {self.__fed_name__}"
            + "==" * 20
        )
        if os.path.exists(self.speech_infos_filename):
            existed_speech_infos = json_load(self.speech_infos_filename)
        else:
            existed_speech_infos = {}
        # 提取每年演讲的信息
        speech_infos = self.extract_speech_infos(existed_speech_infos)

        # 提取已存储的演讲
        if os.path.exists(self.speeches_filename):
            existed_speeches = json_load(self.speeches_filename)
            # 查看已有的最新的演讲日期
            existed_lastest = get_latest_speech_date(existed_speeches)
        else:
            existed_speeches = {}
            # existed_lastest = EARLYEST_EXTRACT_DATE
            existed_lastest = "November 12, 2024"

        # 提取演讲内容
        print(
            "==" * 20
            + f"Start extracting speech content of {self.__fed_name__} from {existed_lastest}"
            + "==" * 20
        )
        speeches = self.extract_speeches(speech_infos, existed_lastest)
        if self.save:
            json_update(self.speeches_filename, speeches)
        return speeches


def test_extract_speech_infos():
    """测试提取演讲信息"""
    richmond = RichmondSpeechScraper()
    speech_infos = richmond.extract_speech_infos()
    print(speech_infos)


def test_extract_single_speech():
    """测试提取单个演讲的内容"""
    richmond = RichmondSpeechScraper()
    speech_info = {
        "year": "2024",
        "date": "June 28, 2024",
        "title": "Why Were Forecasts Off?",
        "href": "https://www.richmondfed.org/press_room/speeches/thomas_i_barkin/2024/barkin_speech_20240628",
        "summary": "President Tom Barkin explores why it has been particularly challenging to predict the path of the economy over the last few years.",
        "speaker": "Tom Barkin",
    }
    speech = richmond.extract_single_speech(speech_info)
    print(speech)


def test():
    richmond = RichmondSpeechScraper(auto_save=True)
    richmond.collect()
    print(
        "="*100
        + "Richmond Scraper Done."
        + "="*100
    )


if __name__ == "__main__":
    # test_extract_single_speech()
    test()
