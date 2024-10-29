#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
@File    :   freser_scraper.py
@Time    :   2024/10/29 14:09:14
@Author  :   wbzhang 
@Version :   1.0
@Desc    :   FRESER数据爬取
'''
import json
import requests
from utils.logger import get_logger

logger = get_logger("FRESERLogger")


class FRESERScraper:
    API_SERVER = "https://fraser.stlouisfed.org"
    API_KEY = "cf24df6c394eb609e20cb6ebabb9dac6"
    URL = "https://www.dallasfed.org/news/speeches"
    __fed_name__ = "FRESER"
    __name__ = f"{__fed_name__.title()}SpeechScraper"
    SAVE_PATH = f"../../data/fed_speeches/{__fed_name__}_fed_speeches/"

    @staticmethod
    def fetch_by_title(params: dict, **kwargs):
        """
        获取单个标题记录
        """
        if not params.get("titleId"):
            logger.warning("请输入标题ID")
            return {}
        else:
            titleId = params.get("titleId")

        # 服务类型
        service_type = kwargs.get("service_type", "/api/title/{titleId}/items")

        params.setdefault("limit", "20")
        params.setdefault("page", "50")
        params.setdefault("format", "json")
        params.setdefault("fields", None)

        # 发送请求
        try:
            response = requests.get(
                url=FRESERScraper.API_SERVER + service_type.format(titleId=titleId),
                params=params,
                headers={"X-API-Key": FRESERScraper.API_KEY},
            )
            result = json.loads(response.content.decode())
        except Exception as e:
            logger.error(f"请求失败，请检查网络连接或参数是否正确。{repr(e)}")
            result = {}

        return result

    @staticmethod
    def fecth_item(item_id: int):
        """
        获取条目
        """
        params = {
            "itemId": item_id,
            "format": "json",
            "fields": None,
        }

        # 发送请求
        try:
            response = requests.get(
                url=FRESERScraper.API_SERVER
                + "/api/item/{itemId}".format(itemId=item_id),
                params=params,
                headers={"X-API-Key": FRESERScraper.API_KEY},
            )
            result = json.loads(response.content.decode())
        except Exception as e:
            logger.error(f"请求失败，请检查网络连接或参数是否正确。{repr(e)}")
            result = {}

        return result


    @staticmethod
    def fecth_title_toc(title_id: int):
        """
        获取标题目录Table of Content
        """
        params = {
            "titleId": title_id,
            "limit": "20",
            "page": "50",
            "format": "json",
            "fields": None,
        }

        # 发送请求
        try:
            response = requests.get(
                url=FRESERScraper.API_SERVER + "/api/title/{titleId}/toc".format(titleId=title_id),
                params=params,
                headers={"X-API-Key": FRESERScraper.API_KEY},
            )
            result = json.loads(response.content.decode())
        except Exception as e:
            logger.error(f"请求失败，请检查网络连接或参数是否正确。{repr(e)}")
            result = {}

        return result


def test_single_title_record():
    params = {
        "titleId": 3767,
        "limit": "20",
        "page": "50",
        "format": "json",
        "fields": None,
    }
    freser = FRESERScraper()
    print(freser.fetch_by_title(params, service_type="/api/title/{titleId}"))


if __name__ == "__main__":
    test_single_title_record()