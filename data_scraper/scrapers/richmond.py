#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    :   richmond.py
@Time    :   2024/09/27 18:26:36
@Author  :   wbzhang
@Version :   1.0
@Desc    :   None
"""

import os
import sys

sys.path.append("../../")
from scraper import SpeechScraper
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from utils.file_saver import json_dump, json_load

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
    __fed_name__ = "richmond_fed"

    def __init__(self, url: str = None, auto_save: bool = True):
        super().__init__(url)
        self.speech_infos_by_year = None
        self.speeches_by_year = None
        os.makedirs(self.SAVE_PATH, exist_ok=True)
        self.save = auto_save

    def expand_all(self, accordian):
        """展开所有年份

        Args:
            accordian (_type_): _description_
        """
        year_links = accordian.find_elements(By.CSS_SELECTOR, "li a[data-anchor-id]")
        for i, link in enumerate(year_links):
            try:
                # year_name = link.text.split("\n")[0] if len(link.text.split("\n")) > 1 else link.text
                link.click()
                # print(f"Year Item: {year_name} done.")
                # 等待加载完
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located(
                        (
                            By.CSS_SELECTOR,
                            f"# pi_center_column > div.component.comp-archive > ul > li:nth-child({i}) > div.content[data-target-id]",
                        )
                    )
                )
            except Exception as e:
                # print(f"Year Item {year_name} is not clickable. {repr(e)}")
                print(repr(e))

    def click_years(self, accordian):
        year_titles = accordian.find_elements(
            By.XPATH,
            "//li //a[starts-with(@href, 'javascript:;')]",
        )

        for title in year_titles:
            try:
                # 检查内容区域是否已经展开
                content_div = title.find_element(
                    By.XPATH, "./following-sibling::div[contains(@class, 'content')]"
                )
                if content_div.get_attribute("style") != "display: block;":
                    # 如果内容区域没有展开，则点击标题
                    title.click()
                    # 等待内容区域展开
                    WebDriverWait(self.driver, 5).until(
                        EC.text_to_be_present_in_element(
                            (
                                By.XPATH,
                                "./following-sibling::div[contains(@class, 'content')]",
                            ),
                            "data-id",
                        )
                    )
                    # 等待内容区域展开
                    # WebDriverWait(self.driver, 10).until(EC.visibility_of(content_div))
            except:
                pass

    def extract_speech_infos(self):
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
        self.click_years(accordian)
        
        # option 2:
        # self.expand_all(accordian)

        speeches_by_year = accordian.find_elements(By.TAG_NAME, "li")
        speech_infos_by_year = {}
        # 获取每一年的演讲
        for single_year_speeches in speeches_by_year:
            # 标题
            year_title = single_year_speeches.find_element(
                By.CSS_SELECTOR, "a[href]"
            ).text
            year = year_title.split("\n")[0]
            # 按数据行进行处理
            data_rows = single_year_speeches.find_elements(
                By.CSS_SELECTOR, "div.content > div.data__row"
            )
            speech_infos_single_year = []
            for data_row in data_rows:
                # 日期
                date = data_row.find_element(
                    By.CSS_SELECTOR,
                    "section > div.data__pub-container > span.data__date",
                ).text
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
                    "year": year,
                    "date": date,
                    "title": title,
                    "href": href,
                    "summary": summary,
                    "speaker": speaker,
                }
                speech_infos_single_year.append(speech_info)
            speech_infos_by_year[year] = speech_infos_single_year
        # 存储到类中
        self.speech_infos_by_year = speech_infos_by_year
        return speech_infos_by_year

    def extract_single_speech(self, speech_info: dict):
        """获取单篇演讲的内容

        Args:
            speech_info (_type_): _description_

        Returns:
            _type_: _description_
        """
        try:
            href = speech_info["href"]
            self.driver.get(href)

            # Wait for the content to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "tmplt.speech"))
            )

            # 演讲标题
            speech_title = self.driver.find_element(
                By.CSS_SELECTOR, "#pi_center_column > div.tmplt.speech > h2"
            ).text
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
                "speech_title": speech_title,
                "highlights": highlights,
                "content": contents,
            }
        except Exception as e:
            print(f"Error when extracting speech content from {href}. Error: {e}")
            speech = {
                "speech_title": "Error",
                "highlights": "Error",
                "content": "Error",
            }
        speech.update(speech_info)
        return speech

    def extract_speeches(self, speech_infos_by_year):
        """搜集每篇演讲的内容"""
        speeches_by_year = {}
        failed = []
        for year, single_year_infos in speech_infos_by_year.items():
            singe_year_speeches = []
            for speech_info in single_year_infos:
                single_speech = self.extract_single_speech(speech_info)
                if single_speech["content"] == "":
                    # 记录提取失败的报告
                    failed.append(single_speech)
                singe_year_speeches.append(single_speech)
            speeches_by_year[year] = singe_year_speeches
            if self.save:
                json_dump(
                    singe_year_speeches,
                    self.SAVE_PATH + f"{self.__fed_name__}_speeches_{year}.json",
                )
        if self.save:
            json_dump(
                failed, self.SAVE_PATH + f"{self.__fed_name__}_failed_speech_infos.json"
            )
            json_dump(
                speeches_by_year, self.SAVE_PATH + f"{self.__fed_name__}_speeches.json"
            )
        return speeches_by_year

    def collect(self):
        """演讲内容收集

        Returns:
            _type_: _description_
        """
        if os.path.exists(self.SAVE_PATH + f"{self.__fed_name__}_speech_infos.json"):
            speech_infos = json_load(
                self.SAVE_PATH + f"{self.__fed_name__}_speech_infos.json"
            )
            print("Speech Infos Data already exists, skip collecting.")
        else:
            # 提取每年演讲的信息
            speech_infos = self.extract_speech_infos()
            if self.save:
                json_dump(
                    speech_infos,
                    self.SAVE_PATH + f"{self.__fed_name__}_speech_infos.json",
                )
        # 提取演讲内容
        speeches = self.extract_speeches(speech_infos)
        if self.save:
            json_dump(speeches, self.SAVE_PATH + f"{self.__fed_name__}_speeches.json")
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
    richmond = RichmondSpeechScraper()
    result = richmond.collect()
    print(result)


if __name__ == "__main__":
    # test_extract_single_speech()
    test()
    
