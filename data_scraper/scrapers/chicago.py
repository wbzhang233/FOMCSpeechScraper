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
from copy import deepcopy
import os
import re
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import time
from datetime import datetime

from data_scraper.scrapers.scraper import SpeechScraper
from utils.common import (
    EARLYEST_EXTRACT_DATE,
    EARLYEST_YEAR,
    get_latest_speech_date,
    parse_datestring,
)
from utils.file_saver import (
    json_dump,
    json_load,
    json_update,
    sort_speeches_dict,
    sort_speeches_records,
    update_records,
)

today = datetime.today()


def regex_date_from_summary(summary: str):
    # 从摘要中匹配日期. Evans-charles 2018-2022年摘要
    pattern = r"presented on (.*?),"
    match = re.search(pattern, summary)
    if match:
        month_date = match.group(1)
    else:
        return ""

    pattern = r", (\d{4}),"
    match = re.search(pattern, summary)
    if match:
        year = match.group(1)
    else:
        return ""

    return f"{month_date}, {year}".strip()


def purified_date(date_str: str):
    """将带-日期字符串标准化.

    Args:
        date_str (str): _description_

    Returns:
        _type_: _description_
    """
    if "-" not in date_str:
        return date_str
    else:
        # 拆分日期和月
        splits = date_str.split(",")
        month, date = splits[0].split(" ")
        date = date.split("-")[-1].strip()
        result = "{month} {date}, {year}".format(
            month=month, date=date, year=splits[1].strip()
        )
        return result


class ChicagoSpeechScraper(SpeechScraper):
    URL = "https://www.chicagofed.org/people/chicago-fed-presidents"
    __fed_name__ = "chicago"
    __name__ = f"{__fed_name__.title()}SpeechScraper"

    def __init__(self, url: str = None, auto_save: bool = True, **kwargs):
        super().__init__(url=url, auto_save=auto_save, **kwargs)
        self.speech_infos_by_year = None
        self.speeches_by_year = None
        self.ERALYEST_YEAR = EARLYEST_YEAR
        # 额外新增：主席任期表信息
        self.presidents_info_filename = os.path.join(
            self.SAVE_PATH, f"{self.__fed_name__}_presidents_info.json"
        )

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
            year = speech["href"].split("/")[-2]
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
            result = speech_date.strftime("%B %d, %Y")
            # 若记录日期为空、或者年份与识别日期年份不一致，则更新日期
            # print(
            #     "{} is going to be replace by {}".format(
            #         speech["date"], speech_date.date().strftime(format="%B %d, %Y")
            #     )
            # )
            return result
        except Exception as e:
            msg = "Error  {} occured when processing {}.".format(
                repr(e), speech["href"]
            )
            print(msg)
            self.logger.info(msg=msg)

        # 再尝试根据摘要匹配日期.
        try:
            result = regex_date_from_summary(speech["summary"])
            result = purified_date(result)
        except Exception as e:
            msg = "Error  {} occured when processing {}.".format(
                repr(e), speech["href"]
            )
            print(msg)
            self.logger.info(msg=msg)
            result = ""

        return result

    def extract_president_infos(self):
        """提取芝加哥历任行长的信息"""
        if os.path.exists(self.presidents_info_filename):
            presidents_infos = json_load(self.presidents_info_filename)
            return presidents_infos

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
                    "name": name,  # 名字
                    "href": href,  # 主页链接
                    "order": order,  # 任期
                    "start_year": start_year,  # 任期开始年份
                    "last_year": last_year,  # 任期结束年份
                }
            )
        # 倒序
        president_infos.reverse()
        json_dump(president_infos, self.presidents_info_filename)
        return president_infos

    def extract_president_speech_infos(
        self, president_info: dict, existed_speech_dates: set
    ):
        """提取芝加哥联储某位行长的演讲信息

        Args:
            president_info (dict): 某位行长的演讲信息
        """
        # 进入主席首页
        href = president_info["href"]
        self.driver.get(href)
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
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
                pdate = parse_datestring(date)
                if pdate:
                    date = pdate.strftime("%B %d, %Y")
                if date in existed_speech_dates:
                    break
                summary = item.text.split("\n")[-1].strip()
                # 按年收纳
                year = str(parse_datestring(date).year)
                speech_infos.setdefault(year, []).append(
                    {
                        "speaker": president_info["name"],
                        "date": date,
                        "title": title,
                        "summary": summary,
                        "href": href,
                    }
                )
                print(
                    f"Speech info of {president_info['name']} {date} {title} collected."
                )
        else:
            # 点击 Speeches
            click_speeches = self.driver.find_element(By.XPATH, "//label[@for='tab7']")
            click_speeches.click()
            WebDriverWait(self.driver, 10.0).until(
                EC.presence_of_element_located((By.XPATH, "//section[@id='speeches']"))
            )
            speech_items = self.driver.find_elements(
                By.XPATH,
                "//section[@id='speeches']/div[@class='peoplePublication__container']",
            )
            for item in speech_items:
                title = item.find_element(By.XPATH, "./div/a[@href]").text.strip()
                href = item.find_element(By.XPATH, "./div/a[@href]").get_attribute(
                    "href"
                )
                # 摘要中也隐含了日期
                p_items = item.find_elements(By.TAG_NAME, "p")
                summary = "\n\n".join([p.text for p in p_items]).strip()
                # 根据href来解析日期
                date = self.extract_speech_date({"href": href, "summary": summary})
                if date in existed_speech_dates:
                    break
                # 查找上一个h3元素
                year = item.find_element(By.XPATH, "./preceding-sibling::h3[1]").text
                speech_infos.setdefault(year, []).append(
                    {
                        "speaker": president_info["name"],
                        "date": date,
                        "title": title,
                        "summary": summary,
                        "href": href,
                    }
                )
                print(
                    f"Speech info of {president_info['name']} {date} {title} collected."
                )
        return speech_infos

    def extract_speech_infos(self, existed_speech_infos: dict):
        """抽取演讲的信息"""
        # 提取历任行长的信息
        president_infos = self.extract_president_infos()
        # 主循环获取所有演讲信息
        speech_infos_by_year = deepcopy(existed_speech_infos)
        for president_info in president_infos:
            # 太早的不要
            if int(president_info["last_year"]) <= 2006:
                continue
            # 获取该行长已存在的演讲日期
            existed_speech_dates = set()
            for _, v in existed_speech_infos.items():
                for speech_info in v:
                    if speech_info["speaker"] == president_info["name"]:
                        existed_speech_dates.add(speech_info["date"])
            # 提取某位行长主页下的演讲信息
            infos = self.extract_president_speech_infos(
                president_info, existed_speech_dates
            )
            for year, new_speech_infos in infos.items():
                if year in speech_infos_by_year:
                    speech_infos_by_year[year] = update_records(
                        speech_infos_by_year.get(year),
                        new_speech_infos,
                    )
                else:
                    speech_infos_by_year[year] = new_speech_infos
                msg = "{number} speech infos of {year} was collected.".format(
                    number=len(speech_infos_by_year[year]), year=year
                )
                print(msg)
                self.logger.info(msg=msg)
        # 排个序
        speech_infos_by_year = OrderedDict(
            sorted(speech_infos_by_year.items(), reverse=True)
        )
        msg = "-" * 50 + "All speech infos was collected." + "-" * 50
        print(msg)
        self.logger.info(msg=msg)
        if self.save and existed_speech_infos != speech_infos_by_year:
            json_update(self.speech_infos_filename, speech_infos_by_year)
        return speech_infos_by_year

    def extract_single_speech(self, speech_info: dict):
        try:
            self.driver.get(speech_info["href"])
            # 等待加载完
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
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
            speech = {**speech_info, "content": content}
        except Exception as e:
            msg = "Error when extracting speech content from {href}. {error}".format(
                href=speech_info["href"], error=repr(e)
            )
            print(msg)
            self.logger.info(msg)
            speech = {**speech_info, "content": ""}
            msg = "{} {} {} content failed.".format(
                speech_info["speaker"], speech_info["date"], speech_info["title"]
            )
            print(msg)
            self.logger.info(msg)
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
                if single_speech["date"] and single_speech["title"]:
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
        # 保存演讲内容
        speeches_by_year = sort_speeches_dict(
            speeches_by_year, required_keys=["date", "title"]
        )
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
    scraper = ChicagoSpeechScraper(
        output_dir="../../data/fed_speeches", log_dir="../../log"
    )
    scraper.collect()


def test_purified_datestr():
    for ds in ["October 9-10, 2024", "October 9, 2024"]:
        print(purified_date(ds))

    result = regex_date_from_summary(
        "A speech presented on May 9, 2019, at the Federal Re"
    )
    print(result)


if __name__ == "__main__":
    # test_extract_speech_infos()
    # test_extract_single_speech()
    test()
    # drop_duplicates_speech_info()
