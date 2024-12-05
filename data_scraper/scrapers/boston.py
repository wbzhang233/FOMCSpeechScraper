#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    :   boston.py
@Time    :   2024/10/24 16:47:09
@Author  :   wbzhang
@Version :   1.0
@Desc    :   1A 波士顿联储银行银行演讲稿数据爬取
"""

from copy import deepcopy
from datetime import datetime
import os
import re
import sys
import time


sys.path.append("../../")

from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.chrome.options import Options
from data_scraper.scrapers.scraper import SpeechScraper
from utils.common import (
    EARLYEST_EXTRACT_DATE,
    STANDRAD_DATE_FORMAT,
    get_latest_speech_date,
    parse_datestring,
)
from utils.pdf_downloader import is_download_existed, read_pdf_file
from utils.file_saver import (
    json_dump,
    json_load,
    json_update,
    sort_speeches_dict,
    unify_speech_dict,
    update_records,
)

# 波士顿联储历任行长任期
BOSTON_PRESIDENT_TIMELINE = {
    "Susan M. Collins": ("July 1, 2022", "present"),
    "Kenneth C. Montgomery": (
        "October 1, 2021",
        "June 30, 2022",
    ),  # 临时行长. 因此position不为President
    "Eric S. Rosengren": ("July 23, 2007", "September 30, 2021"),
    "Cathy E. Minehan": ("July 13, 1994", "July 22, 2007"),
}


def correct(speech_infos_by_year: dict):
    """修正讲话历史数据，尤其是过滤掉非行长以及保留临时代行长的演讲"""
    try:
        new_result = {}
        for year, single_year_infos in speech_infos_by_year.items():
            for i, info in enumerate(single_year_infos):
                if "," in info.get("speaker"):
                    splits = info.get("speaker").split(",")
                    # 舍弃非行长
                    # if not splits[1].strip().startswith("President"):
                    #     continue
                    info["speaker"] = splits[0].strip()
                    # 舍弃非任期内的非行长
                    if (
                        info["speaker"] not in BOSTON_PRESIDENT_TIMELINE
                        # or parse_datestring(info["date"])
                        # < parse_datestring(
                        #     BOSTON_PRESIDENT_TIMELINE.get(info["speaker"])[0]
                        # )
                        # or parse_datestring(info["date"])
                        # > parse_datestring(
                        #     BOSTON_PRESIDENT_TIMELINE.get(info["speaker"])[1]
                        # )
                    ):
                        continue
                    info.setdefault("position", splits[1].strip())
                    info = unify_speech_dict(
                        info, necessary_keys=["speaker", "position", "date", "title"]
                    )
                    new_result.setdefault(year, []).append(info)
                else:
                    # 舍弃非任期内或非行长的演讲
                    if (
                        info["speaker"] not in BOSTON_PRESIDENT_TIMELINE
                        # or parse_datestring(info["date"])
                        # < parse_datestring(
                        #     BOSTON_PRESIDENT_TIMELINE.get(info["speaker"])[0]
                        # )
                        # or parse_datestring(info["date"])
                        # > parse_datestring(
                        #     BOSTON_PRESIDENT_TIMELINE.get(info["speaker"])[1]
                        # )
                    ):
                        continue
                    info.setdefault("position", "President & Chief Executive Officer")
                    info = unify_speech_dict(
                        info, necessary_keys=["speaker", "position", "date", "title"]
                    )
                    new_result.setdefault(year, []).append(info)
    except Exception as e:
        print(f"Error {repr(e)} when correct.")
        new_result = speech_infos_by_year
    return new_result


class BostonSpeechScraper(SpeechScraper):
    URL = "https://www.bostonfed.org/news-and-events/speeches.aspx"
    __fed_name__ = "boston"
    __name__ = f"{__fed_name__.title()}SpeechScraper"

    def __init__(self, url: str = None, auto_save: bool = True, **kwargs):
        # 预设PDF下载存储路径
        pdf_save_dir = kwargs.get("pdf_save_dir", "../data/pdfs/")
        self.DOWNLOAD_PATH = os.path.abspath(
            os.path.join(pdf_save_dir, f"{self.__fed_name__}")
        )
        # PDF文件下载目录
        self.prefs = {
            "download.default_directory": self.DOWNLOAD_PATH,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "plugins.always_open_pdf_externally": True,  # 在外部程序中打开PDF文件
        }
        # 设置浏览器选项
        chrome_options = Options()
        chrome_options.add_experimental_option("prefs", self.prefs)
        super().__init__(url=url, auto_save=auto_save, **kwargs)
        self.speech_infos_by_year = None
        self.speeches_by_year = None

    def extract_speech_date(self, text: str, silent: bool = False):
        """提取段落中的日期

        Args:
            text (str): 段落

        Returns:
            date (str): 日期
        """
        # 正则分段
        try:
            date = ""
            paras = re.split(r"[\n\"·]+", text)
            for para in reversed(paras):
                parse_date = parse_datestring(para.split("|")[0].strip(" \n"))
                if isinstance(parse_date, datetime):
                    date = parse_date.strftime(STANDRAD_DATE_FORMAT)
                else:
                    continue
            if date == "" and not silent:
                print(paras[-1])
        except Exception as e:
            if not silent:
                print(f"Error {repr(e)} when extract speech date.")
            date = ""
        return date

    def parse_single_row(self, data_row: WebElement):
        """解析Boston中的单个演讲信息

        Args:
            data_row (WebElement): 行数据元素

        Returns:
            dict: 讲话信息
        """
        try:
            # 日期和地点
            date_and_location = data_row.find_elements(
                By.CSS_SELECTOR,
                "p.date-and-location",
            )
            if date_and_location:
                date = date_and_location[0].text.split("|")[0].strip()
            else:
                date = self.extract_speech_date(data_row.text)
            # 标题
            title_element = data_row.find_elements(
                By.CSS_SELECTOR, "h1.card-title > a[href]"
            )
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

            # 区分职位和名称
            splits = speaker.split(",", maxsplit=2)
            speaker = splits[0].strip()
            position = splits[-1].strip()
            # 非行长过滤掉,但保留临时行长.
            if (
                not position.startswith("President")
                or speaker not in BOSTON_PRESIDENT_TIMELINE
            ):
                return None

            speech_info = {
                "speaker": speaker,
                "position": position,
                "date": date,
                "title": title,
                "summary": summary,
                "href": href,
            }
        except Exception as e:
            print(f"Parse Speech Info Error: {e}")
            speech_info = None

        return speech_info

    def extract_speech_infos(self, existed_speech_infos: dict):
        """提取每篇演讲的链接、标题、日期和讲话人信息

        Returns:
            _type_: _description_
        """
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "main-content"))
        )
        # 点击expanda all
        expand_all = self.driver.find_element(
            By.XPATH, "/html/body/main/div[1]/div[2]/div/div[1]/a[2]"
        )
        expand_all.click()
        # Wait for the content to load
        WebDriverWait(self.driver, 10.0).until(
            EC.presence_of_element_located(
                (By.XPATH, "/html/body/main/div[1]/div[2]/div/div[2]")
            )
        )

        panel_group = self.driver.find_element(
            By.XPATH, "/html/body/main/div[1]/div[2]/div/div[2]"
        )
        speeches_by_year = panel_group.find_elements(By.CLASS_NAME, "panel")

        # 已经存储的日期.
        existed_speech_dates = set()
        for _, single_year_infos in existed_speech_infos.items():
            existed_speech_dates.update([info["date"] for info in single_year_infos])

        speech_infos_by_year = deepcopy(existed_speech_infos)
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
            speech_infos_single_year = []
            _count = 0
            for data_row in data_rows:
                # 第一行为空
                if not data_row.text.strip():
                    continue
                speech_info = self.parse_single_row(data_row)
                if not speech_info:
                    continue
                # 如果日期已存在，则跳出循环.
                if speech_info and (
                    speech_info.get("date")  # 日期不为空才能解析
                    and (
                        speech_info["date"] in existed_speech_dates
                        or parse_datestring(speech_info["date"])
                        < parse_datestring(EARLYEST_EXTRACT_DATE)
                    )
                ):
                    break
                if speech_info and speech_info.get("href").startswith(
                    "https://www.bostonfed.org/"
                ):
                    print(
                        "{date} | {title}. {speaker}\n".format(
                            date=speech_info["date"],
                            title=speech_info["title"],
                            speaker=speech_info["speaker"],
                        )
                    )
                    speech_infos_single_year.append(speech_info)
                    _count += 1
            print(
                "-" * 50
                + f"{_count} speech infos of {year} has been extracted."
                + "-" * 50
                + "\n"
            )
            speech_infos_by_year[year] = update_records(
                speech_infos_by_year.get(year), speech_infos_single_year
            )
            counts += len(speech_infos_single_year)
        # 存储到类中
        print(f"Extracted {counts} speeches from Boston Fed.")
        speech_infos_by_year = sort_speeches_dict(speech_infos_by_year)
        if self.save and speech_infos_by_year != existed_speech_infos:
            json_update(self.speech_infos_filename, speech_infos_by_year)
        return speech_infos_by_year

    def extract_content_from_pdf(self, href: str):
        try:
            if href.endswith(".pdf"):
                # 下载PDF文件
                pdf_filename = href.split("/")[-1]
                # 如果不存在，就下载
                _times = 0
                while (
                    not is_download_existed(self.DOWNLOAD_PATH + pdf_filename)
                ) and _times <= 2:
                    self.driver.get(href)
                    time.sleep(1.0)
                    _times += 1
                # 如果下载完成，则解析
                if is_download_existed(self.DOWNLOAD_PATH + pdf_filename):
                    # 解析pdf
                    content = read_pdf_file(self.DOWNLOAD_PATH + pdf_filename)
                else:
                    content = f"$PDF$: {pdf_filename}"
                return content
        except Exception as e:
            print(f"Parse Speech Content Error: {e}")
            return f"$HREF$: {href}"

    def extract_single_speech(self, speech_info: dict):
        """提取单篇演讲的内容

        Args:
            speech_info (dict): 演讲信息

        Returns:
            _type_: _description_
        """
        try:
            href = speech_info["href"]
            self.driver.get(href)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located((By.ID, "main-content"))
            )

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
            # 如果存在PDF下载链接，则下载并且解析. 使用PDF全文文档作为内容，否则使用段落
            download_buttons = self.driver.find_elements(
                By.CSS_SELECTOR, "div > a[href$='.pdf'][download].main-segment"
            )
            if len(download_buttons) != 0:
                # 获取下载链接
                download_link = download_buttons[0].get_attribute("href")
                contents = self.extract_content_from_pdf(download_link)
            else:
                # 内容
                content_elements = self.driver.find_element(
                    By.CSS_SELECTOR,
                    "#main-content > div.bodytextlist > div.container > div.row > div.col-sm-10.col-md-8.center-block > div.tag-box-container",
                )
                contents = content_elements.text
            speech = {
                **speech_info,
                "highlights": highlights,
                "content": contents,
            }
        except Exception as e:
            print(f"Error when extracting speech content from {href}. Error: {repr(e)}")
            speech = {
                **speech_info,
                "highlights": "",
                "content": "",
            }
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
            for speech_info in single_year_infos:
                # 如果日期为空，则跳过
                if not speech_info["date"] or speech_info["date"] == "":
                    continue
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
                        "Extract {speaker} {date} {title} failed.".format(
                            speaker=speech_info["speaker"],
                            date=speech_info["date"],
                            title=speech_info["title"],
                        )
                    )
                single_year_speeches.append(single_speech)
            speeches_by_year[year] = update_records(
                speeches_by_year.get(year), single_year_speeches
            )
            if self.save:
                json_update(
                    os.path.join(
                        self.SAVE_PATH, f"{self.__fed_name__}_speeches_{year}.json"
                    ),
                    single_year_speeches,
                )
            print(f"Speeches of {year} collected.")
        # 保存演讲内容
        if self.save:
            # 保存读取失败的演讲内容
            json_dump(failed, self.failed_speech_infos_filename)
        # 更新已存储的演讲内容
        speeches_by_year = sort_speeches_dict(
            speeches_by_year, required_keys=["date", "title"]
        )
        if self.save and speeches_by_year != existed_speeches:
            json_update(self.speeches_filename, speeches_by_year)
        return speeches_by_year

    def collect(self):
        """收集每篇演讲的信息

        Returns:
            dict: 演讲内容 dict<year, list[dict]>
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
    scraper = BostonSpeechScraper(
        output_dir="../../data/fed_speeches",
        log_dir="../../log",
        pdf_save_dir="../../data/pdfs",
    )
    scraper.collect()


def correct_speeches():
    speeches = json_load(
        "../../data/fed_speeches/boston_fed_speeches/boston_speeches.json",
    )
    speeches = correct(speeches)
    json_dump(
        speeches, "../../data/fed_speeches/boston_fed_speeches/boston_speeches.json"
    )


if __name__ == "__main__":
    # test_extract_speech_infos()
    # test_extract_single_speech()
    test()
    # correct_speeches()
