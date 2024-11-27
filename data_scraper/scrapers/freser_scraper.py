#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    :   freser_scraper.py
@Time    :   2024/10/29 14:09:14
@Author  :   wbzhang
@Version :   1.0
@Desc    :   FRESER数据爬取
"""

import json
import requests
# from requests.exceptions import (
#     HTTPError,
#     ConnectionError,
#     Timeout,
#     TooManyRedirects,
#     RequestException,
# )
from utils.logger import get_logger

logger = get_logger("FRESERLogger", log_filepath="../../log/")

ALL_FIELDS = "!".join(
    [
        "titleInfo",
        "language",
        "note",
        "location",
        "name",
        "physicalDescription",
        "subject",
        "accessCondition",
        "typeOfResource",
        "abstract",
        "classification",
        "genre",
        "tableOfContents",
        "relatedItem",
        "extension",
        "originInfo",
        "targetAudience",
        "identifier",
        "recordInfo",
    ]
)


class FRESERScraper:
    API_SERVER = "https://fraser.stlouisfed.org"
    API_KEY = "cf24df6c394eb609e20cb6ebabb9dac6"
    URL = "https://www.dallasfed.org/news/speeches"
    __fed_name__ = "FRESER"
    __name__ = f"{__fed_name__.title()}SpeechScraper"
    SAVE_PATH = f"../../data/fed_speeches/{__fed_name__}_fed_speeches/"
    # 超时时长
    TIMEOUT = 10.0

    @staticmethod
    def fetch_txt(txt_url: str):
        """获取TXT文本内容

        Args:
            txt_url (str): txt网址

        Returns:
            str: txt文本内容
        """
        if not txt_url.endswith(".txt"):
            msg = "{} is not txt url.".format(txt_url)
            print(msg)
            return "$NOT TXT URL$"
        try:
            response = requests.get(txt_url, timeout=FRESERScraper.TIMEOUT)
            response.raise_for_status()  # 检查响应状态码是否为200
            result = response.text
        # except HTTPError as http_err:
        #     print(f"HTTP error occurred: {http_err}")
        #     result = "$HTTPERROR$"
        # except ConnectionError as conn_err:
        #     print(f"Connection error occurred: {conn_err}")
        #     result = "$CONNECTION ERROR$"
        # except Timeout as timeout_err:
        #     print(f"Timeout error occurred: {timeout_err}")
        #     result = "$TIMEOUT ERROR$"
        # except TooManyRedirects as redirect_err:
        #     print(f"Too many redirects error occurred: {redirect_err}")
        #     result = "$TOOMANY REDIRECTS ERROR$"
        # except RequestException as req_err:
        #     print(f"Request error occurred: {req_err}")
        #     result = "$REQUEST EXCEPTION$"
        except Exception as e:
            msg = f"Failed to fetch text. Error: {repr(e)}"
            # logger.error(msg)
            print(msg)
            result = ""

        return result

    @staticmethod
    def fetch_single_title_record(title_id: int, params: dict = {}, **kwargs):
        """
        获取单个标题记录
        """
        params.setdefault("limit", "1000")
        params.setdefault("page", "50")
        params.setdefault("format", "json")
        params.setdefault("fields", ALL_FIELDS)

        # 发送请求
        try:
            response = requests.get(
                url=FRESERScraper.API_SERVER
                + "/api/title/{titleId}".format(titleId=title_id),
                params=params,
                headers={"X-API-Key": FRESERScraper.API_KEY},
                timeout=FRESERScraper.TIMEOUT,
            )
            result = json.loads(response.content.decode())
        except Exception as e:
            logger.error(f"Failed to fetch single title record. Error: {repr(e)}")
            result = {}

        return result

    @staticmethod
    def fetch_title_items(title_id: int, params: dict = {}, **kwargs):
        """
        获取单个标题记录
        """
        # 服务类型
        service_type = kwargs.get("service_type", "/api/title/{titleId}/items")
        params.setdefault("limit", "1000")
        params.setdefault("page", "50")
        params.setdefault("format", "json")
        params.setdefault("fields", ALL_FIELDS)

        # 发送请求
        try:
            response = requests.get(
                url=FRESERScraper.API_SERVER + service_type.format(titleId=title_id),
                params=params,
                headers={"X-API-Key": FRESERScraper.API_KEY},
                timeout=FRESERScraper.TIMEOUT,
            )
            result = json.loads(response.content.decode())
        except Exception as e:
            logger.error(f"Failed to fetch title items. Error: {repr(e)}")
            result = {}

        return result

    @staticmethod
    def fecth_title_toc(title_id: int, **kwargs):
        """
        获取标题目录Table of Content
        """
        # 发送请求
        try:
            response = requests.get(
                url=FRESERScraper.API_SERVER
                + "/api/title/{titleId}/toc".format(titleId=title_id),
                headers={"X-API-Key": FRESERScraper.API_KEY},
                timeout=FRESERScraper.TIMEOUT,
            )
            result = json.loads(response.content.decode())
        except Exception as e:
            logger.error(f"Failed to fetch single title toc. Error: {repr(e)}")
            result = {}

        return result

    @staticmethod
    def fecth_item(item_id: int, params: dict = {}, **kwargs):
        """
        获取条目
        """
        params.setdefault("limit", "1000")
        params.setdefault("page", "50")
        params.setdefault("format", "json")
        params.setdefault("fields", ALL_FIELDS)

        # 发送请求
        try:
            response = requests.get(
                url=FRESERScraper.API_SERVER
                + "/api/item/{itemId}".format(itemId=item_id),
                params=params,
                headers={"X-API-Key": FRESERScraper.API_KEY},
                timeout=FRESERScraper.TIMEOUT,
            )
            response = json.loads(response.content.decode())
            result = response["records"][0]
        except Exception as e:
            logger.error(f"获取Item {item_id}的信息遇到错误. {repr(e)}")
            result = {}

        return result


def test_single_title_record():
    freser = FRESERScraper()
    print(freser.fetch_single_title_record(title_id=3767))


def test_title_items():
    freser = FRESERScraper()
    print(freser.fetch_title_items(title_id=3767))


def test_title_toc():
    freser = FRESERScraper()
    print(freser.fecth_title_toc(title_id=3767))


def test_fetch_txt():
    # text_url = "https://fraser.stlouisfed.org/files/text/historical/frbsl_history/presidents/oneill/oneill-20231128.txt"
    text_url = "https://fraser.stlouisfed.org/files/text/historical/frbsl_history/presidents/bullard/bullard_20110317.txt"
    freser = FRESERScraper()
    print(freser.fetch_txt(txt_url=text_url))


if __name__ == "__main__":
    # test_single_title_record()
    # test_title_items()
    # test_title_toc()
    test_fetch_txt()
