#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    :   stlouis.py
@Time    :   2024/10/29 15:25:47
@Author  :   wbzhang
@Version :   1.0
@Desc    :   8H 圣路易斯联储主席讲话数据爬虫
"""

import os
import time
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException
from data_scraper.scrapers.scraper import SpeechScraper
from data_scraper.scrapers.freser_scraper import FRESERScraper
from utils.common import get_latest_speech_date, parse_datestring
from utils.file_saver import (
    json_dump,
    json_load,
    json_update,
    sort_speeches_dict,
    update_dict,
)


class StLouisSpeechScraper(SpeechScraper):
    # 前任行长们的系列
    URL = "https://fraser.stlouisfed.org/series/statements-speeches-presidents-federal-reserve-bank-st-louis-3767"
    # 现任行长的言论
    URL_CURRENT = "https://www.stlouisfed.org/from-the-president/remarks"
    __fed_name__ = "stlouis"
    __name__ = f"{__fed_name__.title()}SpeechScraper"

    def __init__(self, url: str = None, auto_save: bool = True, **kwargs):
        super().__init__(url=url, auto_save=auto_save, **kwargs)
        # 按年度整理的演讲信息、演讲记录
        self.speech_infos_by_year = None
        self.speeches_by_year = None
        # 标题信息
        self.title_infos_filename = os.path.join(
            self.SAVE_PATH, f"{self.__fed_name__}_title_infos.json"
        )

    def fetch_series_all_titles(self):
        """提取FRESER上某个series的所有子title

        Args:
            title_infos (list[dict]):
        """
        title_infos = []
        # 打开圣路易斯联储讲话集合
        self.driver.get(self.URL)
        # 等待主内容加载完
        titles = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//ul[@class='browse-by-list']/li"))
        )
        for title in titles:
            title.click()
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
                title_id = href.split("/")[-1]
            except Exception as e:
                msg = "Error when fetching series titles: {}".format(repr(e))
                print(msg)
                href = None
                title_id = None
            title_infos.append(
                {"title": title_name, "href": href, "title_id": title_id}
            )
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
                "date": "",
                "text_url": "",
                "year": "Unknown",
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
                "date": date,
                "text_url": text_url,
                "year": year,
            }
        except Exception as e:
            msg = "Error {} occured when fetching item content".format(repr(e))
            print(msg)
            return {
                "date": "",
                "text_url": "",
                "year": "Unknown",
            }

    def fetch_title_all_items(self, title_info: str):
        """搜集某个title下所有讲话的文本数据

        Args:
            title_link (str): _description_
        """
        speaker = title_info["title"].split("of")[-1].strip()
        # 搜集每个讲话的数据, 直接使用title-toc接口获取 (无法调通)
        result = FRESERScraper.fecth_title_toc(title_id=int(title_info["title_id"]))
        if result and len(result) != 0:
            return result

        # 开始爬取每篇报告的text_url
        self.driver.get(title_info["href"])
        # 等待所有元素可用
        WebDriverWait(self.driver, 5).until(
            EC.visibility_of_all_elements_located(
                (
                    By.XPATH,
                    "//div[@class='browse-by-list list']/ul/li/a[@data-id and @id]",
                )
            )
        )
        result = {}
        # 点击每一个年代
        decade_buttons = self.driver.find_elements(
            By.XPATH,
            "//ul[@class='navbar-nav']/li[(@data-section) and (contains(@class, 'nav-item jump-to-section'))]",
        )
        for decade in decade_buttons:
            decade.click()
            # 等待所有元素可用
            time.sleep(2.0)
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
                    speech.update(
                        {
                            "speaker": speaker,
                            "title": item_name,
                            "href": item_link,
                            "item_id": item_id,
                        }
                    )
                    print(
                        "Item {item_id} {speaker} {title} {date} was collected.".format(
                            item_id=item_id,
                            speaker=speaker,
                            title=item_name,
                            date=speech["date"],
                        )
                    )
                    result.setdefault(speech["year"], []).append(speech)
                except StaleElementReferenceException as e:  # type: ignore
                    msg = f"item failed. {repr(e)}"
                    print(msg)
                    self.logger.warning(msg)
                except Exception as e:
                    msg = f"item {item} failed. {repr(e)}"
                    print(msg)
                    self.logger.warning(msg)
                    continue

        return result

    def extract_speech_infos(self):
        """提取演讲的基本信息

        Returns:
            speech_infos_by_year (dict): 按年整理的演讲的基本信息. dict<year, list[dict]>
        """
        # 搜寻历任主席的title链接
        if os.path.exists(self.title_infos_filename):
            title_infos = json_load(self.title_infos_filename)
        else:
            # 获取St. Louis集合下的历任行长的FRESER-title信息
            title_infos = self.fetch_series_all_titles()
            json_update(self.title_infos_filename, title_infos)
        msg = f"{len(title_infos)} titles found."
        print(msg)
        print("-" * 100)
        self.logger.info(msg)
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
                tag_field=["speaker", "date", "title"],
                sort_field="date",
            )
            # 记录日志
            print("=" * 80)
            msg = f"{president} has {len(speeches)} speeches collected."
            print("=" * 80)
            self.logger.info(msg=msg)

        speech_infos_by_year = sort_speeches_dict(
            speech_infos_by_year,
            sort_filed="date",
            required_keys=["date", "title"],
            tag_fields=["href"],
        )
        self.speech_infos_by_year = speech_infos_by_year
        # 更新基本信息.
        if self.save:
            json_update(self.speech_infos_filename, speech_infos_by_year)
        return speech_infos_by_year

    def extract_single_speech(self, speech_info: dict):
        """抽取单片讲话数据的内容

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
            speech = {**speech_info, "content": content}
        except Exception as e:
            print(
                "Error when extracting speech content from {href}. {error}".format(
                    href=speech_info["href"], error=repr(e)
                )
            )
            speech = {**speech_info, "content": ""}
            print(
                "{}, {}, {} content failed.".format(
                    speech_info["speaker"], speech_info["date"], speech_info["title"]
                )
            )
        return speech

    def extract_current_speech_content(self, href: str):
        """根据链接获取演讲正文

        Args:
            href (str): _description_
        """
        try:
            self.driver.get(href)
            paras = WebDriverWait(self.driver, 5.0).until(
                EC.presence_of_all_elements_located(
                    (By.XPATH, "//div[@class='field-content']//p")
                )
            )
            contents = "\n\n".join([para.text.strip() for para in paras])
        except Exception as e:
            print(f"Error {repr(e)} when extract contents.")
            contents = ""
        return contents

    def collect_speeches_of_current_president(self):
        """获取现任行长的演讲稿

        Args:
            start_date (str): _description_
        """
        self.driver.get(self.URL_CURRENT)
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_all_elements_located(
                (By.XPATH, "//div[@class='field-content']")
            )
        )
        speeches = {}
        try:
            # 根据大标题寻找 演讲人
            frbstl = self.driver.find_element(By.XPATH, '//*[@id="frbstl-content"]')
            speaker = (
                frbstl.text.strip()
                .lstrip("President ")
                .rstrip("'s Remarks and Community Engagement")
                .strip()
            )
            # 内容元素
            field_content_element = self.driver.find_element(
                By.XPATH, "//div[@class='field-content']"
            )
            # 寻找到标题
            h2_title = field_content_element.find_element(By.TAG_NAME, "h2")
            # 寻找下一个包含strong和a元素的兄弟节点
            next_p = h2_title.find_element(
                By.XPATH, "following-sibling::p[a and strong][1]"
            )
            while next_p:
                # 寻找到日期
                speech_date = (
                    next_p.find_element(By.TAG_NAME, "strong").text.strip().rstrip(":")
                )
                # 日期处理.
                month_date, year = speech_date.split(",", maxsplit=2)
                year = year.strip()
                month, date = month_date.split(" ", maxsplit=2)
                month = month.strip()
                date = date.strip().split("-")[-1].strip()
                speech_date = pd.to_datetime(f"{month} {date}, {year}").date()
                # 摘要
                abstract = next_p.text.strip()
                # 寻找到演讲标题
                link = next_p.find_element(By.CSS_SELECTOR, "a[href]")
                href = link.get_attribute("href")
                speech_title = link.text.strip()
                # 按年度进行整理
                speeches.setdefault(year, []).append(
                    {
                        "speaker": speaker,
                        "date": speech_date.strftime("%B %d, %Y"),
                        "title": speech_title,
                        "abstract": abstract,
                        "href": href,
                    }
                )
                # 寻找到下一个演讲内容
                following_siblings = next_p.find_elements(
                    By.XPATH, "following-sibling::p[a and strong]"
                )
                if len(following_siblings) == 0:
                    break
                else:
                    next_p = following_siblings[0]
        except Exception as e:
            print(
                f"Error {repr(e)} occured when collecting the speeches' info of current president."
            )
            pass
        
        # 将演讲信息更新到speech_infos中
        if self.save:
            json_update(self.speech_infos_filename, speeches)

        # 遍历获取正文
        for year, single_year_speeches in speeches.items():
            for i, speech in enumerate(single_year_speeches):
                content = self.extract_current_speech_content(speech["href"])
                speeches[year][i].update({"content": content})
            if self.save:
                # 将该年的内容更新到已有数据中
                json_update(
                    os.path.join(
                        self.SAVE_PATH, f"{self.__fed_name__}_speeches_{year}.json"
                    ),
                    speeches[year],
                )

        return speeches

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
                    os.path.join(
                        self.SAVE_PATH, f"{self.__fed_name__}_speeches_{year}.json"
                    ),
                    single_year_speeches,
                )
            print(
                "{} speeches of {} collected.".format(len(speeches_by_year[year]), year)
            )
        speeches_by_year = sort_speeches_dict(
            speeches_by_year,
            sort_filed="date",
            required_keys=["speaker", "date", "title"],
            tag_fields=["href"],
        )
        if self.save:
            # 更新读取失败的演讲内容
            json_dump(failed, self.failed_speech_infos_filename)
            json_update(self.speeches_filename, speeches_by_year)
        return speeches_by_year

    def collect_speeches_of_former_presidents(self):
        """收集每篇演讲的信息

        Returns:
            dict: 按自然年份整理的讲话数据. dict<str, list[dict]>
        """
        # 先收集历任行长演讲的基本信息（不含正文和highlights等）
        if os.path.exists(self.speech_infos_filename):
            # 若已经存在基本信息，则加载进来.
            speech_infos = json_load(self.speech_infos_filename)
            # 查看已有的最新的演讲日期
            existed_lastest = get_latest_speech_date(speech_infos)
            self.logger.info("Speech Infos Data already exists, skip collecting infos.")
            # existed_lastest = "October 01, 2023"
        else:
            # 否则，去获取基本信息
            speech_infos = self.extract_speech_infos()
            if self.save:
                json_dump(speech_infos, self.speech_infos_filename)
            existed_lastest = "Jan. 01, 2024"

        # 提取演讲正文内容
        print("-" * 100)
        print("Extract speeches start from {}".format(existed_lastest))
        print("-" * 100)
        # 获取历史行长的演讲记录
        speeches = self.extract_speeches(speech_infos, existed_lastest)
        return speeches

    def collect(self, mode: str = "Update"):
        """收集所有历任行长的讲话数据

        Args:
            mode (str, optional): 数据模式. Defaults to "Update", 表示仅获取现任行长讲话数据.
        """
        print(
            "==" * 20
            + f"Start collecting speech infos of {self.__fed_name__}"
            + "==" * 20
        )
        if mode == "Update":
            speeches = self.collect_speeches_of_current_president()
        elif mode == "All":
            # 先爬取现在的
            speeches = self.collect_speeches_of_current_president()
            print("-" * 100)
            print("Speeches of Current president was scraped.")
            # 在爬取历史前任行长的
            former_speeches = self.collect_speeches_of_former_presidents()
            print("Speeches of Fromer presidents was scraped.")
            speeches = update_dict(speeches, former_speeches)
        else:
            msg = "mode {mode} was not supported. Only `All` and `Update` was valid."
            print(msg)
        # 保存
        if self.save:
            json_update(self.speeches_filename, speeches)
        print(
            "==" * 20
            + f"Speech infos of {self.__fed_name__} has collected."
            + "==" * 20
        )


def test_extract_speech_infos():
    """测试 extract_speeches 信息 方法"""
    scraper = StLouisSpeechScraper()
    speech_infos = scraper.extract_speech_infos()
    print(speech_infos)


def test_extract_single_speech():
    """测试 extract_single_speech 方法"""
    scraper = StLouisSpeechScraper()
    speech_info = {}

    speech = scraper.extract_single_speech(speech_info)
    print(speech)


def test():
    scraper = StLouisSpeechScraper(
        output_dir="../../data/fed_speeches", log_dir="../../log"
    )
    scraper.collect(mode="Update")


if __name__ == "__main__":
    # test_extract_speech_infos()
    # test_extract_single_speech()
    test()
