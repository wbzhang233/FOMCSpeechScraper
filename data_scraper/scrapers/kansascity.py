#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    :   kansas_city.py
@Time    :   2024/10/22 16:30:49
@Author  :   wbzhang
@Version :   1.0
@Desc    :   10J 堪萨斯城联储讲话数据爬取
"""

import os
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
    NoSuchElementException,
)

import time
import requests

from data_scraper.scrapers.scraper import SpeechScraper
from utils.common import parse_datestring
from utils.file_saver import json_dump, json_load, json_update
from utils.logger import logger
from collections import OrderedDict
from PyPDF2 import PdfReader


def read_pdf_file(pdf_filename: str):
    if os.path.exists(pdf_filename):
        reader = PdfReader(pdf_filename)
        print(">--|--<" * 20)
        print("{} has been read.".format(pdf_filename))
        return "\n\n".join([page.extract_text() for page in reader.pages]).strip("\n ")
    else:
        return ""


def download_pdf(pdf_url: str, file_name: str, save_path: str):
    response = requests.get(pdf_url)

    if response.status_code == 200:
        with open(f"{save_path}/{file_name}", "wb") as f:
            f.write(response.content)
        print("PDF {} downloaded successfully.".format(file_name))
    else:
        print("Failed to download PDF. Status code:", response.status_code)


def is_download_complete(download_dir):
    for file in os.listdir(download_dir):
        if file.endswith(".crdownload"):
            return False
    return True


def is_download_existed(filepath: str):
    if os.path.exists(filepath):
        return True
    else:
        return False


class KansasCitySpeechScraper(SpeechScraper):
    URL = "https://www.kansascityfed.org/speeches/"
    __fed_name__ = "kansascity"
    __name__ = f"{__fed_name__.title()}SpeechScraper"
    SAVE_PATH = f"../../data/fed_speeches/{__fed_name__}_fed_speeches/"
    DOWNLOAD_PATH = "C:/Users/Administrator/Downloads/"

    # PDF文件下载目录
    prefs = {
        "download.default_directory": SAVE_PATH,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True,  # 在外部程序中打开PDF文件
    }

    def __init__(self, url: str = None, auto_save: bool = True):
        # 设置浏览器选项
        chrome_options = Options()
        chrome_options.add_experimental_option("prefs", self.prefs)
        super().__init__(url, options=chrome_options)
        self.speech_infos_by_year = None
        self.speeches_by_year = None
        os.makedirs(self.SAVE_PATH, exist_ok=True)
        print(f"{self.SAVE_PATH} has been created.")
        self.save = auto_save

    def extract_speech_infos(self):
        """抽取演讲的信息"""
        try:
            # 设置speakers
            filter_buttons = self.driver.find_elements(
                By.XPATH,
                "//div[@search-filter-category-group]/div[@class='button-dropdown']/button[@type='button']",
            )
            filter_buttons[0].click()
            speaker_filter = self.driver.find_element(By.NAME, "6-12")
            select = Select(speaker_filter)
            select.select_by_visible_text("Thomas M. Hoenig")
            select.select_by_visible_text("Esther L. George")
            select.select_by_visible_text("Jeffrey Schmid")
            # 选取
            person_elements = speaker_filter.find_elements(
                By.XPATH,
                "./following-sibling::div[@class='options']/ul[@select-name='6-12']/li/span",
            )
            for person_ele in person_elements:
                if person_ele.text in [
                    "Thomas M. Hoenig",
                    "Esther L. George",
                    "Jeffrey Schmid",
                ]:
                    person_ele.click()
            # 设置话题
            filter_buttons[1].click()
            topic_filter = self.driver.find_element(By.NAME, "6-13")
            select = Select(topic_filter)
            select.select_by_visible_text("All")
            # 选中checkbox
            all_element = topic_filter.find_element(
                By.XPATH,
                "./following-sibling::div[@class='options']/ul[@select-name='6-13']/li[@value='all']",
            )
            all_element.click()
            # 点击apply_filters
            apply_filter_button = self.driver.find_element(
                By.XPATH,
                "//button[(@type='button') and (contains(text(), 'Apply Filters'))]",
            )
            apply_filter_button.click()

            # 等待页面
            time.sleep(3.0)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located((By.XPATH, "//*[@id='mainContent']"))
            )

            # 设置每页展示100个
            perpage_number_button = self.driver.find_element(
                By.XPATH,
                "//*[@id='search']/footer/div/form/div/div[2]/div/div/button",
            )
            perpage_number_button.click()
            # # 好像不起作用
            # perpage = self.driver.find_element(By.NAME, "perpage")
            # select = Select(perpage)
            # select.select_by_value("100")
            # 直接选择控件点击
            perpage_100 = self.driver.find_element(
                By.XPATH, "//ul[@select-name='perpage']/li[@value='100']"
            )
            perpage_100.click()
            # 等待页面
            time.sleep(5.0)
            WebDriverWait(self.driver, 10).until(
                EC.visibility_of_all_elements_located((By.CLASS_NAME, "clear"))
            )
        except Exception as e:
            print(f"Error setting date range: {e}")

        # 主循环获取所有演讲信息
        speech_infos_by_year = {}
        while True:
            speech_items = self.driver.find_elements(
                By.XPATH, "//div[@class='result-list']/div[@class='clear']"
            )
            for item in speech_items:
                # 提取日期
                date = item.find_element(
                    By.XPATH, ".//span[contains(@class, 'date')]/time"
                ).text.strip()
                year = int(date.split(",")[-1].strip())
                if year not in speech_infos_by_year:
                    speech_infos_by_year[year] = []
                # 提取演讲者
                speaker = item.find_element(
                    By.XPATH, ".//a[@class='mnt-tag-group-staff-link' and @href]"
                ).text.strip()

                # 提取标题和链接
                title_link = item.find_element(By.XPATH, ".//h3/a[@href]")
                title = title_link.text.strip()
                href = title_link.get_attribute("href")

                speech_infos_by_year[year].append(
                    {
                        "date": date,
                        "speaker": speaker,
                        "title": title,
                        "href": href,
                    }
                )

            try:
                next_page_button = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "a[href][search-pagination-form-next-page-button][aria-label='Go to Next Page']",
                )
                next_page_button.click()
                # 等待页面加载
                time.sleep(2.0)
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

        speech_infos_by_year = OrderedDict(speech_infos_by_year.items())
        self.speech_infos_by_year = speech_infos_by_year
        return speech_infos_by_year

    def extract_single_speech(self, speech_info: dict):
        speech = {"speaker": "", "content": ""}
        try:
            href = speech_info["href"]
            if href.endswith(".pdf"):
                # 下载PDF文件
                pdf_filename = href.split("/")[-1]
                # 如果不存在，就下载
                _times = 0
                while (not is_download_existed(self.DOWNLOAD_PATH + pdf_filename)) and _times<=10:
                    self.driver.get(href)
                    time.sleep(1.0)
                    _times +=1
                # 如果下载完成，则解析
                if is_download_existed(self.DOWNLOAD_PATH + pdf_filename):
                    # 解析pdf
                    content = read_pdf_file(self.DOWNLOAD_PATH + pdf_filename)
                else:
                    content = f"$PDF$: {pdf_filename}"
                speech = {
                    "content": content,
                }
            elif href.startswith("https://www.youtube.com/"):
                speech = {
                    "content": f"$YOUTUBE$: {href}",
                }
            else:
                # 爬取所有p元素
                speech = {
                    "content": f"$UNSUPPORTED$: {href}",
                }
        except Exception as e:
            print(
                "Error when extracting speech content from {href}. {error}".format(
                    href=href, error=repr(e)
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
        if not os.path.exists(self.SAVE_PATH + f"{self.__fed_name__}_speech_infos.json"):
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
            # existed_lastest = "Jan 01, 2006"
            existed_lastest = "Oct 21, 2024"

        # 提取演讲正文内容
        speech_infos = OrderedDict(speech_infos.items())
        speeches = self.extract_speeches(speech_infos, existed_lastest)
        return speeches


def test_extract_single_speech():
    """测试 extract_single_speech 方法"""
    scraper = KansasCitySpeechScraper()
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
    scraper = KansasCitySpeechScraper()
    speech_infos = scraper.extract_speech_infos()
    print(speech_infos)


def test():
    scraper = KansasCitySpeechScraper()
    scraper.collect()


if __name__ == "__main__":
    test()
