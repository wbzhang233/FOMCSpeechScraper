#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    :   common.py
@Time    :   2024/09/29 17:42:47
@Author  :   wbzhang
@Version :   1.0
@Desc    :   公共方法
"""

from datetime import datetime
import pandas as pd
import re

date_patterns = [
    r"""
^(January|February|March|April|May|June|July|August|September|October|November|December)\s+  # 月份
(\d{1,2}),\s+  # 日，带逗号
(\d{4})$       # 年份
""",  # %B %d, %Y
    r"""
^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+  # 月份
(\d{1,2}),\s+  # 日，带逗号
(\d{4})$       # 年份
""",  # %b %d, %Y
    r"""
^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec).\s+  # 月份
(\d{1,2}),\s+  # 日，带逗号
(\d{4})$       # 年份
""",  # %b. %d, %Y
]

STANDRAD_DATE_FORMAT = "%B %d, %Y"
EARLYEST_YEAR = 2006
EARLYEST_EXTRACT_DATE = "Jan 01, 2006"


def parse_datestring(
    date_str: str, format: str = None, silent: bool = False
) -> datetime:
    """日期字符串标准化

    Args:
        date_str (str): 日期字符串

    Returns:
        datetime: 日期
    """
    if not date_str:
        return None
    try:
        result = pd.to_datetime(date_str, format=format).to_pydatetime()
        return result
    except Exception as e:
        if not silent:
            print(
                "date string {} transformed to datetime failed. {}".format(
                    date_str, repr(e)
                )
            )
        pass

    try:
        if re.fullmatch(date_patterns[0], date_str, re.IGNORECASE | re.VERBOSE):
            result = datetime.strptime(date_str, "%B %d, %Y")
        elif re.fullmatch(date_patterns[1], date_str, re.IGNORECASE | re.VERBOSE):
            date_str = date_str.replace("Sept", "Sep").replace("sept", "sep")
            result = datetime.strptime(date_str, "%b %d, %Y")
        elif re.fullmatch(date_patterns[2], date_str, re.IGNORECASE | re.VERBOSE):
            date_str = date_str.replace("Sept", "Sep").replace("sept", "sep")
            result = datetime.strptime(date_str, "%b. %d, %Y")
        else:
            result = date_str
        return result
    except ValueError as e:
        msg = f"Parse datestring {date_str} failed. {repr(e)}"
        if not silent:
            print(msg)
        raise ValueError(msg=msg)
    except Exception as e:
        msg = f"Parse datestring {date_str} failed. {repr(e)}"
        if not silent:
            print(date_str + f" | {repr(e)}")
        raise Exception(msg=msg)


def get_latest_speech_date(obj: dict | list):
    """获取字典中演讲的最新日期"""
    if isinstance(obj, dict):
        # 查看已有的最新的演讲日期
        dates = []
        for _, v in obj.items():
            for x in v:
                dates.append(parse_datestring(x["date"]))
    elif isinstance(obj, list):
        dates = []
        for x in obj:
            dates.append(parse_datestring(x["date"]))
    else:
        msg = f"TypeError: unsupported type {type(obj)}."
        print(msg)
        dates = []
    return max(dates).strftime("%b %d, %Y") if dates else None


def test_parse_datestring():
    dates = []
    for year_str in [
        "Sep 23, 2024",
        "Oct 23, 1995",
        "Sept 23, 2024",
        "Sept. 25, 2024",
        "May 06, 2024",
        "March 20, 1997",
    ]:
        date = parse_datestring(year_str)
        print(date)
        dates.append(date)
    print(max(dates))


if __name__ == "__main__":
    test_parse_datestring()
