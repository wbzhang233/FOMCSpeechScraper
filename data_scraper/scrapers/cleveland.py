#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    :   cleveland.py
@Time    :   2024/09/27 18:26:46
@Author  :   wbzhang
@Version :   1.0
@Desc    :   4D 克利夫兰联储行长讲话数据爬取
"""

from copy import deepcopy
from datetime import datetime
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC

from bs4 import BeautifulSoup

from data_scraper.scrapers.scraper import SpeechScraper
from utils.common import EARLYEST_EXTRACT_DATE, get_latest_speech_date, parse_datestring
from utils.file_saver import (
    json_dump,
    json_load,
    json_update,
    sort_speeches_dict,
    sort_speeches_records,
)


class ClevelandSpeechScraper(SpeechScraper):
    URL = "https://www.clevelandfed.org/collections/speeches"
    __fed_name__ = "cleveland"
    __name__ = f"{__fed_name__.title()}SpeechScraper"

    def __init__(self, url: str = None, auto_save: bool = True, **kwargs):
        super().__init__(url=url, auto_save=auto_save, **kwargs)
        self.speech_infos_by_year = None
        self.speeches_by_year = None

    def setting_date_range(self):
        """设置时间范围"""
        try:
            # 设置时间范围为最早和最晚
            from_years_element = self.driver.find_element(By.ID, "fromYears")
            from_years_options = [
                int(option.text)
                for option in Select(from_years_element).options
                if option.text.isdigit()
            ]
            from_years_element.send_keys(str(min(from_years_options)))
            # 最晚时间框
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
        except Exception as e:
            print(f"Error setting date range: {e}")

    def extract_speech_infos(self, existed_speech_infos: dict):
        """抽取演讲的信息"""
        # 设置时间范围
        # 等待页面
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "fromYears"))
        )
        self.setting_date_range()

        # 已经存储的日期.
        existed_speech_dates = set()
        for _, single_year_infos in existed_speech_infos.items():
            existed_speech_dates.update([info["date"] for info in single_year_infos])

        # 主循环获取所有演讲信息
        speech_infos_by_year = deepcopy(existed_speech_infos)
        _continue = True
        while _continue:
            soup = BeautifulSoup(self.driver.page_source, "html.parser")
            speech_items = soup.find_all("li", class_="result-item")

            for item in speech_items:
                # 提取日期
                date = (
                    item.find("div", class_="date-reference")
                    .text.split(" | ")[0]
                    .strip()
                )
                year = int(date.split(".")[2])
                date = datetime.strptime(date, "%m.%d.%Y").strftime("%B %d, %Y")
                # 如果元素已经在列表中，则跳过
                if date in existed_speech_dates:
                    print(f"Date {date} already exists in the list. Continue.")
                    _continue = False
                    break
                # 提取演讲者
                speaker = item.find("span", class_="author-name").text.strip()

                # 提取标题和链接
                title_link = item.find("a", href=True)
                title = title_link.text.strip()
                href = title_link["href"]

                # 提取描述
                description = (
                    item.find("div", class_="page-description").find("p").text.strip()
                    if item.find("div", class_="page-description")
                    else ""
                )

                speech_infos_by_year.setdefault(year, []).append(
                    {
                        "speaker": speaker,
                        "date": date,
                        "title": title,
                        "href": f"https://www.clevelandfed.org{href}",
                        "highlights": description,
                    }
                )

            if not _continue:
                break
            # # Try to find and click the "Next" button
            try:
                next_button = self.driver.find_element(
                    By.CSS_SELECTOR, "li.page-selector-item-next:not(.disabled) a"
                )
                self.driver.execute_script("arguments[0].click();", next_button)
                # 等待页面加载
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_all_elements_located(
                        (
                            By.XPATH,
                            "//*[@id='content']/div[3]/div[1]/search-results/div",
                        )
                    )
                )
            except Exception as e:
                print(f"Error occurred while clicking the next button: {e}")
                break

        # 更新保存
        speech_infos_by_year = sort_speeches_dict(
            speech_infos_by_year, sort_filed="date", required_keys=["href"]
        )
        if self.save and speech_infos_by_year != existed_speech_infos:
            json_update(self.speech_infos_filename, speech_infos_by_year)
        print(f"Speech infos of {self.__fed_name__} have been extracted.")
        return speech_infos_by_year

    def extract_single_speech(self, speech_info: dict):
        try:
            self.driver.get(speech_info["href"])
            # 等待加载完
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "content"))
            )
            # 主内容元素
            main_content = self.driver.find_element(By.ID, "content")
            rich_text = main_content.find_element(
                By.XPATH,
                '//*[@id="content"]/div[3]/div[1]/div/div[1]/div/div[4]/div',
            )
            if rich_text:
                content = "\n\n".join(
                    [
                        p.text.strip()
                        for p in rich_text.find_elements(By.CSS_SELECTOR, "p, h2")
                    ]
                )
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
                "{} {} {} content failed. Error: {}".format(
                    speech_info["speaker"],
                    speech_info["date"],
                    speech_info["title"],
                    repr(e),
                )
            )
            speech = {**speech_info, "content": ""}
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
            # 跳过之前的年份
            if int(year) < start_year:
                continue
            single_year_speeches = []
            for speech_info in single_year_infos:
                # 跳过start_date之前的演讲
                if parse_datestring(speech_info["date"]) <= start_date:
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
                elif single_speech.get("date") and single_speech.get("title"):
                    single_year_speeches.append(single_speech)
            speeches_by_year[year] = sort_speeches_records(single_year_speeches)
            if self.save:
                json_update(
                    os.path.join(
                        self.SAVE_PATH, f"{self.__fed_name__}_speeches_{year}.json"
                    ),
                    single_year_speeches,
                )
            print(f"Speeches of {year} collected.")
        speeches_by_year = sort_speeches_dict(
            speeches_by_year,
            required_keys=["speaker", "date", "title"],
            tag_fields=["href"],
        )
        # 保存演讲内容
        if self.save:
            # 保存读取失败的演讲内容
            json_dump(failed, self.failed_speech_infos_filename)
        if self.save and speeches_by_year != existed_speeches:
            # 更新已存储的演讲内容
            json_update(self.speeches_filename, speeches_by_year)
        return speeches_by_year

    def collect(self):
        """收集每篇演讲的信息

        Returns:
            dict: 按自然年整理的演讲内容
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
            existed_lastest = EARLYEST_EXTRACT_DATE

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
    scraper = ClevelandSpeechScraper()
    speech_info = {
        "date": "February 24, 2020",
        "speaker": "Loretta J. Mester",
        "title": "The Outlook for the Economy and Monetary Policy in 2020",
        "href": "https://www.clevelandfed.org/collections/speeches/sp-20200224-outlook-for-the-economy-and-monetary-policy-in-2020",
        "highlights": "Speech by Loretta J. Mester, President and Chief Executive Officer, Federal Reserve Bank of Cleveland - The Outlook for the Economy and Monetary Policy in 2020 - 36th Annual NABE Economic Policy Conference - Washington, DC - February 24, 2020",
    }

    speech = scraper.extract_single_speech(speech_info)
    print(speech)


def test_extract_speech_infos():
    """测试 extract_speeches 信息 方法"""
    scraper = ClevelandSpeechScraper()
    speech_infos = scraper.extract_speech_infos()
    print(speech_infos)


def test():
    scraper = ClevelandSpeechScraper(
        output_dir="../../data/fed_speeches", log_dir="../../log"
    )
    scraper.collect()


if __name__ == "__main__":
    test()
