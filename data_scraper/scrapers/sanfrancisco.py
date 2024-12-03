#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    :   san_francisco.py
@Time    :   2024/09/30 15:02:17
@Author  :   wbzhang
@Version :   1.0
@Desc    :   12L 旧金山联储历任主席讲话数据爬取
"""

from copy import deepcopy
import os
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    WebDriverException,
)

import time

from data_scraper.scrapers.scraper import SpeechScraper
from utils.common import get_latest_speech_date, parse_datestring
from utils.file_saver import (
    json_dump,
    json_load,
    json_update,
    unify_speech_dict,
    update_records,
    sort_speeches_dict,
)


class SanFranciscoSpeechScraper(SpeechScraper):
    URL = "https://www.frbsf.org/news-and-media/speeches/"
    __fed_name__ = "sanfrancisco"
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
        self.speeches_filename = self.SAVE_PATH + f"{self.__fed_name__}_speeches.json"
        self.failed_speech_infos_filename = (
            self.SAVE_PATH + f"{self.__fed_name__}_failed_speech_infos.json"
        )

    def choose_presidents(self):
        """点击直选中"""
        president_filter = self.driver.find_elements(
            By.XPATH, '//*[@id="wp--skip-link--target"]/div/div[2]/div[2]/div/div'
        )
        for button in president_filter:
            if "leadership speeches" in button.text.lower():
                continue
            else:
                try:
                    # button.click()
                    self.driver.execute_script("arguments[0].click();", button)
                except WebDriverException as e:
                    print(f"Clicking button failed: {e}")
                    continue
                except Exception as e:
                    print(f"Button failed: {e}")
                    pass
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    '//*[@id="wp--skip-link--target"]/div/div[2]/div[1]/div/div/div[contains(@class, "fwpl-result r")]',
                )
            )
        )

    def extract_speech_infos(self, existed_speech_infos: dict):
        """抽取演讲的信息"""
        # 选中行长
        self.choose_presidents()
        # 已经存储的日期.
        existed_speech_dates = set()
        for _, single_year_infos in existed_speech_infos.items():
            existed_speech_dates.update([info["date"] for info in single_year_infos])

        # 主循环获取所有演讲信息
        speech_infos_by_year = deepcopy(existed_speech_infos)

        _continue = True
        while _continue:
            speech_items = self.driver.find_elements(
                By.XPATH, "//div[contains(@class, 'fwpl-result r')]"
            )

            for item in speech_items:
                # 提取日期
                try:
                    date = item.find_element(
                        By.CSS_SELECTOR, "div.fwpl-item.el-julyf"
                    ).text.strip()
                except Exception as e:
                    print(f"Fetching speech date failed: {e}")
                    continue
                # 查看是否已经在爬取过的日期中
                if date in existed_speech_dates:
                    _continue = False
                    break
                year = date.split(",")[-1].strip()
                # 提取演讲者
                speaker_elements = item.find_elements(
                    By.CSS_SELECTOR, "span.fwpl-term.fwpl-tax-speech-series"
                )
                if speaker_elements:
                    speaker = speaker_elements[0].text.strip()
                    speaker = re.sub(r"['’]*s* Speeches", "", speaker)
                    speaker = re.sub(r"['’]*S* SPEECHES", "", speaker).title()
                else:
                    speaker = ""
                if speaker.lower() in ["leadership speeches"]:
                    continue
                # 提取标题和链接
                title_link = item.find_element(By.CSS_SELECTOR, "a[href]")
                title = title_link.text.strip()
                href = title_link.get_attribute("href")
                speech_infos_by_year.setdefault(year, []).append(
                    {
                        "speaker": speaker,
                        "date": date,
                        "title": title,
                        "href": href,
                    }
                )
                print("Info of {} {} | {} extracted.".format(speaker, date, title))
            if not _continue:
                break
            # Try to find and click the "Next" button
            try:
                next_button = self.driver.find_element(
                    By.CSS_SELECTOR, "a.facetwp-page.next:not(.disabled)"
                )
                self.driver.execute_script("arguments[0].click();", next_button)
                # 等待页面加载
                time.sleep(2.0)
            except Exception as e:
                print(
                    f"Next button not found or disabled. Reached last page. {repr(e)}"
                )
                break

        # 去重并且排序
        speech_infos_by_year = sort_speeches_dict(
            speech_infos_by_year,
            sort_filed="date",
            required_keys=["speaker", "date", "title", "href"],
            tag_fields=["href"],
        )
        if self.save and speech_infos_by_year != existed_speech_infos:
            json_update(self.speech_infos_filename, speech_infos_by_year)
        return speech_infos_by_year

    def extract_single_speech(self, speech_info: dict):
        try:
            self.driver.get(speech_info["href"])
            # 等待加载完
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "wp--skip-link--target"))
            )

            # NEW 剔除footnotes之后的部分
            options = [
                '//*[@id="toc_Footnotes"]',
                '//*[@id="wp--skip-link--target"]/div[2]/div/div[2]/div[1]/p[strong and contains(text(), "Footnotes")]',
            ]

            footnotes_elements = self.driver.find_elements(By.XPATH, " | ".join(options))
            if len(footnotes_elements)!=0:
                content_elements = footnotes_elements[0].find_elements(
                    By.XPATH, "./preceding-sibling::p[not(a)]"
                )
            else:
                content_elements = self.driver.find_elements(
                    By.XPATH,
                    '//*[@id="wp--skip-link--target"]/div[2]/div/div[2]/div[1]/p[not(a)]',
                )

            if content_elements:
                content = "\n\n".join(
                    [
                        p.text.strip()
                        for p in content_elements
                    ]
                )
                print(
                    "{}. {} | {} content extracted.".format(
                        speech_info["speaker"],
                        speech_info["date"],
                        speech_info["title"],
                    )
                )
            else:
                content = ""
                print(
                    "{}. {} | {} content failed.".format(
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
        return unify_speech_dict(
            speech, necessary_keys=["speaker", "date", "title", "content"]
        )

    def extract_speeches(
        self, speech_infos_by_year: dict, existed_speeches: dict, start_date: str
    ):
        """搜集每篇演讲的内容"""
        # 获取演讲的开始时间
        start_date = parse_datestring(start_date)
        start_year = start_date.year

        speeches_by_year = deepcopy(existed_speeches)
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
                # 跳过不为行长的演讲
                if 'leadership' in speech_info['speaker'].lower():
                    continue
                single_speech = self.extract_single_speech(speech_info)
                if single_speech["content"] == "":
                    # 记录提取失败的报告
                    failed.append(single_speech)
                singe_year_speeches.append(single_speech)
            speeches_by_year[year] = update_records(
                speeches_by_year.get(year), singe_year_speeches,
                tag_fields=['speaker', 'date', 'title']
            )
            if self.save:
                print(f"Year:{year} | {len(singe_year_speeches)} speeches of {self.__fed_name__} was collected.")
                json_update(
                    self.SAVE_PATH + f"{self.__fed_name__}_speeches_{year}.json",
                    singe_year_speeches,
                )
        
        if self.save:
            json_dump(failed, self.failed_speech_infos_filename)
        # 去重并且排序
        speeches_by_year = sort_speeches_dict(
            speeches_by_year,
            sort_filed="date",
            required_keys=["speaker", "date", "title", "content"],
            tag_fields=["date", "href"],
        )
        if self.save and speeches_by_year != existed_speeches:
            json_update(self.speeches_filename, speeches_by_year)
        return speeches_by_year

    def collect(self):
        """收集每篇演讲的信息

        Returns:
            dict: 演讲信息
        """
        # 提取每年演讲的基本信息（不含正文和highlights等）
        print(
            "==" * 20
            + f"Start collecting speech infos of {self.__fed_name__}"
            + "==" * 20
        )
        # # 载入已存储的演讲信息
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


def test_extract_single_speech():
    """测试 extract_single_speech 方法"""
    scraper = SanFranciscoSpeechScraper()
    speech_info = {
        "content": "",
        "date": "Mary C. Daly’s Speeches",
        "speaker": "Mary C. Daly’s Speeches",
        "title": "Version Two",
        "href": "https://www.frbsf.org/news-and-media/speeches/mary-c-daly/2024/05/version-two",
        "location": "Mary C. Daly’s Speeches",
    }

    speech = scraper.extract_single_speech(speech_info)
    print(speech)


def test_extract_speech_infos():
    """测试 extract_speeches 信息 方法"""
    scraper = SanFranciscoSpeechScraper()
    speech_infos = scraper.extract_speech_infos()
    print(speech_infos)


def test():
    scraper = SanFranciscoSpeechScraper()
    scraper.collect()


if __name__ == "__main__":
    # test_extract_speech_infos()
    # test_extract_single_speech()
    test()
