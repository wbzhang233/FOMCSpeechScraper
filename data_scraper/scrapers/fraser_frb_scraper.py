#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    :   fraser_frb_scraper.py
@Time    :   2024/11/21 16:23:08
@Author  :   wbzhang
@Version :   1.0
@Desc    :   FRASER 爬取十二家地区联储银行行长讲话的爬虫
"""

import os
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException
from freser_scraper import FRESERScraper
from utils.common import parse_datestring
from utils.file_saver import (
    json_dump,
    json_load,
    json_update,
    sort_speeches_dict,
    update_dict,
)


class FRASERFRBSpeechScraper:
    def __init__(self, url: str, frb_name: str, auto_save: bool = True, **kwargs):
        self.URL = url
        self.__frb_name__ = frb_name
        # 爬虫名称
        self.__name__ = f"{self.__frb_name__.title()}SpeechScraper"
        # 存储目录
        self.SAVE_PATH = "../../data/frb_speeches/{}/".format(self.__frb_name__)
        # 存储变量
        self.speech_infos_by_year = None
        self.speeches_by_year = None
        os.makedirs(self.SAVE_PATH, exist_ok=True)
        print(f"{self.SAVE_PATH} has been created.")
        self.save = auto_save
        # 打开主页s
        options = kwargs.get("options", None)
        self.driver = webdriver.Chrome(options=options)
        # self.driver.get(self.URL)
        print(f"{self.__name__} is ready.")

    def fetch_series_all_titles(self):
        """提取FRESER上某个series的所有子title

        Args:
            title_infos (list[dict]):
        """
        title_infos = []
        # 打开圣路易斯联储讲话集合
        self.driver.get(self.URL)
        # 等待主内容加载完
        time.sleep(2.0)
        WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable(
                (By.XPATH, "//ul[@class='browse-by-list']/li[span]")
            )
        )
        title = self.driver.find_element(
            By.XPATH, "//ul[@class='browse-by-list']/li[span]"
        )
        while title:
            title.click()
            time.sleep(3.0)
            WebDriverWait(self.driver, 10).until(
                EC.visibility_of_all_elements_located(
                    (By.XPATH, "//div[contains(@class, 'browse-by-right')]")
                )
            )
            # 名称
            title_name = title.text

            # 获取链接
            try:
                # 切换对话窗
                dialog = self.driver.find_element(
                    By.XPATH, "//div[@class='modal-dialog' and @role='document']"
                )

                href = dialog.find_element(
                    By.XPATH, "//input[@id='share-url' and @value]"
                ).get_attribute("value")
                # title-id
                title_id = href.split("/")[-1].split("-")[-1]
                assert title_id.isdigit(), "奇怪的事情发生了. {href}后缀不是title_id."
            except AssertionError as e:
                pass
            except Exception as e:
                msg = "Error when fetching series titles: {}".format(repr(e))
                print(msg)
                href = None
                title_id = None
            title_infos.append(
                {"title": title_name, "href": href, "title_id": title_id}
            )
            # 寻找下一个兄弟节点
            follow_siblings = title.find_elements(
                By.XPATH, "following-sibling::li[span][1]"
            )
            if len(follow_siblings) == 0:
                break
            else:
                title = follow_siblings[0]
        return title_infos

    @staticmethod
    def fetch_item_info(item_id: str):
        """获取Item的信息

        Args:
            item_id (str): _description_

        Returns:
            _type_: _description_
        """
        if not item_id.isdigit():
            return {
                "year": "Unknown",
                "date": "",
                "text_url": "",
            }
        try:
            # 打开链接，找到下载按键 -> 找到text_url，获取
            response = FRESERScraper.fecth_item(item_id=item_id)
            response = response["records"][0]
            # 获取日期 dateIssued
            date = parse_datestring(response["originInfo"]["sortDate"])
            year = str(date.year)
            date = date.strftime("%B %d, %Y")
            # text_url
            text_url = response["location"]["textUrl"][0]
            return {
                "year": year,
                "date": date,
                "text_url": text_url,
            }
        except Exception as e:
            msg = "Error {} occured when fetching item content".format(repr(e))
            print(msg)
            return {
                "year": "Unknown",
                "date": "",
                "text_url": "",
            }

    def fetch_title_all_items(self, title_info: str):
        """搜集某个title下所有讲话的文本数据

        Args:
            title_link (str): _description_
        """
        # 如果不是title，就跳过.
        if title_info["href"].split('/')[-2] != "title":
            print("{} is not a FRASER title.".format(title_info["href"]))
            return {}
        # 演讲人
        speaker = title_info["title"].split("of")[-1].strip()
        # 搜集每个讲话的数据, 直接使用title-toc接口获取 (无法调通)
        try:
            if (
                not isinstance(title_info["title_id"], str)
                or not title_info["title_id"].isdigit()
            ):
                msg = "{} is not title id.".format(title_info["title_id"])
                return {}
            result = FRESERScraper.fecth_title_toc(title_id=int(title_info["title_id"]))
            if result and len(result) != 0:
                return result
        except Exception as e:
            msg = "通过fetch title toc接口获取title_id: {}失败. Error: {}".format(
                title_info["title_id"], repr(e)
            )
            pass

        # 开始爬取每篇报告的text_url
        self.driver.get(title_info["href"])
        locator = (
            By.XPATH,
            "//ul[@class='navbar-nav']/li[(@data-section) and (contains(@class, 'nav-item jump-to-section'))]",
        )
        WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable(locator))
        result = {}
        # 点击每一个年代
        decade_buttons = self.driver.find_elements(locator[0], locator[1])
        for decade in decade_buttons:
            # 过滤年代
            decade_str = decade.text.strip("").rstrip("s")
            if decade_str not in ["2000", "2010", "2020", "2030"]:
                continue
            decade.click()
            # 等待所有元素可用
            time.sleep(1.0)
            WebDriverWait(self.driver, 5).until(
                EC.visibility_of_all_elements_located(
                    (
                        By.XPATH,
                        "//div[@class='browse-by-list list']/ul/li/a[@data-id and @id]",
                    )
                )
            )
            # 找到所有条目，搜集链接
            items = self.driver.find_elements(
                By.XPATH,
                "//div[@class='browse-by-list list']/ul[@data-section='{section_name}']/li/a[@data-id and @id]".format(
                    section_name=decade.text
                ),
            )
            for item in items:
                try:
                    # 标题
                    item_name = item.text.strip()
                    # 链接
                    item_link = item.get_attribute("href")
                    item_id = item.get_attribute("data-id")
                    # 获取演讲条目的内容
                    speech = self.fetch_item_info(item_id)
                    # 只保留2006年后的speech item
                    if (
                        isinstance(speech["year"], str)
                        and speech["year"].isdigit()
                        and int(speech["year"]) >= 2006
                    ):
                        speech.update(
                            {
                                "item_id": item_id,
                                "speaker": speaker,
                                "title": item_name,
                                "href": item_link,
                            }
                        )
                        result.setdefault(speech["year"], []).append(speech)
                        print(
                            "Item {item_id}. {speaker} | {title} | {date} was collected.".format(
                                item_id=item_id,
                                speaker=speaker,
                                title=item_name,
                                date=speech["date"],
                            )
                        )
                except StaleElementReferenceException as e:  # type: ignore
                    msg = f"item failed. {repr(e)}"
                    print(msg)
                except Exception as e:
                    msg = f"item {item} failed. {repr(e)}"
                    print(msg)
                    continue

        return result

    def extract_speech_infos(self):
        """提取演讲的基本信息

        Returns:
            speech_infos_by_year (dict): 按年整理的演讲的基本信息. dict<year, list[dict]>
        """
        # 搜寻历任主席的title链接
        if os.path.exists(self.SAVE_PATH + f"{self.__frb_name__}_title_infos.json"):
            title_infos = json_load(
                self.SAVE_PATH + f"{self.__frb_name__}_title_infos.json"
            )
        else:
            # 获取St. Louis集合下的历任行长的FRESER-title信息
            title_infos = self.fetch_series_all_titles()
            json_update(
                self.SAVE_PATH + f"{self.__frb_name__}_title_infos.json", title_infos
            )
        msg = f"{len(title_infos)} titles found."
        print(msg)
        print("-" * 100)
        # 根据每个行长的title链接，分别搜索演讲items的讲话内容
        speech_infos_by_year = {}
        for title_info in title_infos:
            # 搜集某个行长的讲话
            president = title_info["title"].split("of")[-1].strip()
            # 搜集某位行长的讲话，按year进行整理
            speeches = self.fetch_title_all_items(title_info=title_info)
            # 按年份整理
            update_dict(
                speech_infos_by_year,
                speeches,
                # tag_field=["speaker", "date", "title"],
                # sort_field="date",
            )
            # 记录日志
            print("=" * 80)
            msg = f"{president} has {len(speeches)} speeches collected."
            print("=" * 80)

        self.speech_infos_by_year = sort_speeches_dict(speech_infos_by_year)
        # 更新基本信息.
        json_update(
            self.SAVE_PATH + f"{self.__frb_name__}_speech_infos.json",
            speech_infos_by_year,
        )
        return speech_infos_by_year

    def extract_single_speech(self, speech_info: dict):
        """抽取单个讲话数据的内容

        Args:
            speech_info (dict): 单篇演讲的信息

        Returns:
            dict: 包含content等其他信息的演讲信息
        """
        try:
            # 获取演讲正文
            content = FRESERScraper.fetch_txt(speech_info["text_url"])
            print(
                "Content of {}, {}, {} extracted.".format(
                    speech_info["speaker"], speech_info["date"], speech_info["title"]
                )
            )
            speech = {**speech_info, **{"content": content}}
        except Exception as e:
            print(
                "Error when extracting speech content from {href}. {error}".format(
                    href=speech_info["href"], error=repr(e)
                )
            )
            speech = {**speech_info, **{"content": ""}}
            print(
                "{}, {}, {} content failed.".format(
                    speech_info["speaker"], speech_info["date"], speech_info["title"]
                )
            )
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
                # 跳过start_date之前的演讲
                if parse_datestring(speech_info["date"]) <= start_date:
                    print(
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
                    print(
                        "Extract {speaker}, {date}, {title} failed.".format(
                            speaker=speech_info["speaker"],
                            date=speech_info["date"],
                            title=speech_info["title"],
                        )
                    )
                single_year_speeches.append(single_speech)
            speeches_by_year[year] = single_year_speeches
            # 按年度保存演讲
            if self.save:
                json_update(
                    self.SAVE_PATH + f"{self.__frb_name__}_speeches_{year}.json",
                    single_year_speeches,
                )
            print(
                "{} speeches of {} collected.".format(len(speeches_by_year[year]), year)
            )
        if self.save:
            # 更新读取失败的演讲内容
            json_dump(
                failed,
                self.SAVE_PATH + f"{self.__frb_name__}_failed_speech_infos.json",
            )
        return speeches_by_year

    def collect(self):
        """收集每篇演讲的信息

        Returns:
            dict: 按自然年份整理的讲话数据. dict<str, list[dict]>
        """
        # 先收集历任行长演讲的基本信息（不含正文和highlights等）
        if os.path.exists(
            self.SAVE_PATH + f"{self.__frb_name__}_speech_infos.json"
        ):
            # 若已经存在基本信息，则加载进来.
            speech_infos = json_load(
                self.SAVE_PATH + f"{self.__frb_name__}_speech_infos.json"
            )
            # 查看已有的最新的演讲日期
            latest_year = max([k for k, _ in speech_infos.items() if k.isdigit()])
            existed_lastest = max(
                [
                    parse_datestring(speech_info["date"])
                    for speech_info in speech_infos[latest_year]
                ]
            ).strftime("%b %d, %Y")
            print("Speech Infos Data already exists, skip collecting infos.")
            # existed_lastest = "October 01, 2023"
        else:
            # 否则，去获取基本信息
            speech_infos = self.extract_speech_infos()
            if self.save:
                json_dump(
                    speech_infos,
                    self.SAVE_PATH + f"{self.__frb_name__}_speech_infos.json",
                )
            existed_lastest = "Jan. 01, 2006"

        # 提取演讲正文内容
        print("-" * 100)
        print("Extract speeches start from {}".format(existed_lastest))
        print("-" * 100)
        # 获取历史行长的演讲记录
        speeches = self.extract_speeches(speech_infos, existed_lastest)
        speeches = sort_speeches_dict(speeches)
        json_update(self.SAVE_PATH + f"{self.__frb_name__}_speeches.json", speeches)
        return speeches


def test_extract_speech_infos():
    """测试 extract_speeches 信息 方法"""
    scraper = FRASERFRBSpeechScraper()
    speech_infos = scraper.extract_speech_infos()
    print(speech_infos)


def test_extract_single_speech():
    """测试 extract_single_speech 方法"""
    scraper = FRASERFRBSpeechScraper()
    speech_info = {}

    speech = scraper.extract_single_speech(speech_info)
    print(speech)


SERIES_MAPPING = [
    # {
    #     "url": "https://fraser.stlouisfed.org/series/statements-speeches-presidents-federal-reserve-bank-boston-9014",
    #     "series_id": 9014,
    #     "frb_name": "boston",
    # },
    {
        "url": "https://fraser.stlouisfed.org/series/statements-speeches-presidents-federal-reserve-bank-new-york-6744",
        "series_id": 6744,
        "frb_name": "newyork",
    },
    {
        "url": "https://fraser.stlouisfed.org/series/statements-speeches-presidents-federal-reserve-bank-philadelphia-4516",
        "series_id": 4516,
        "frb_name": "philadelphia",
    },
    {
        "url": "https://fraser.stlouisfed.org/series/statements-speeches-presidents-federal-reserve-bank-cleveland-3764",
        "series_id": 3764,
        "frb_name": "cleveland",
    },
    {
        "url": "https://fraser.stlouisfed.org/series/statements-speeches-presidents-federal-reserve-bank-richmond-6826",
        "series_id": 6826,
        "frb_name": "richmond",
    },
    {
        "url": "https://fraser.stlouisfed.org/series/statements-speeches-presidents-federal-reserve-bank-atlanta-5168",
        "series_id": 5168,
        "frb_name": "atlanta",
    },
    {
        "url": "https://fraser.stlouisfed.org/series/statements-speeches-presidents-federal-reserve-bank-chicago-5968",
        "series_id": 5968,
        "frb_name": "chicago",
    },
    {
        "url": "https://fraser.stlouisfed.org/series/statements-speeches-presidents-federal-reserve-bank-st-louis-3767",
        "series_id": 3767,
        "frb_name": "st-louis",
    },
    {
        "url": "https://fraser.stlouisfed.org/series/statements-speeches-presidents-federal-reserve-bank-minneapolis-3765",
        "series_id": 3765,
        "frb_name": "minneapolis",
    },
    {
        "url": "https://fraser.stlouisfed.org/series/statements-speeches-presidents-federal-reserve-bank-kansas-city-9271",
        "series_id": 9271,
        "frb_name": "kansas-city",
    },
    {
        "url": "https://fraser.stlouisfed.org/series/statements-speeches-presidents-federal-reserve-bank-dallas-6145",
        "series_id": 6145,
        "frb_name": "dallas",
    },
    {
        "url": "https://fraser.stlouisfed.org/series/statements-speeches-presidents-federal-reserve-bank-san-francisco-3766",
        "series_id": 3766,
        "frb_name": "san-francisco",
    },
    {
        "url": "https://fraser.stlouisfed.org/series/statements-speeches-federal-open-market-committee-participants-3761",
        "series_id": 3761,
        "frb_name": "fomc_participants",
    },
]

SERIES_URL_PREFIX = "https://fraser.stlouisfed.org/series/{series_id}"


def test():
    for item in SERIES_MAPPING:
        print("=====" * 20)
        print("{} is starting...".format(item["frb_name"]))
        scraper = FRASERFRBSpeechScraper(url=item["url"], frb_name=item["frb_name"])
        scraper.collect()
        print("{} over.".format(item["frb_name"]))


if __name__ == "__main__":
    # test_extract_speech_infos()
    # test_extract_single_speech()
    test()