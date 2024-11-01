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


def parse_datestring(date_str: str, format: str=None) -> datetime:
    """日期字符串标准化

    Args:
        date_str (_type_): _description_

    Returns:
        _type_: _description_
    """
    if not date_str:
        return None
    try:
        result = pd.to_datetime(date_str, format=format).to_pydatetime()
        return result
    except Exception as e:
        print("date string {} transformed to datetime failed. {}".format(date_str, repr(e)))
        pass

    try:
        if re.fullmatch(date_patterns[0], date_str, re.IGNORECASE | re.VERBOSE):
            return datetime.strptime(date_str, "%B %d, %Y")
        elif re.fullmatch(date_patterns[1], date_str, re.IGNORECASE | re.VERBOSE):
            date_str = date_str.replace('Sept', 'Sep').replace('sept', 'sep')
            return datetime.strptime(date_str, "%b %d, %Y")
        elif re.fullmatch(date_patterns[2], date_str, re.IGNORECASE | re.VERBOSE):
            date_str = date_str.replace("Sept", "Sep").replace("sept", "sep")
            return datetime.strptime(date_str, "%b. %d, %Y")
        else:
            return date_str
    except ValueError as e:
        print(date_str + f" | {repr(e)}")
        return date_str
    except Exception as e:
        print(date_str + f" | {repr(e)}")
        return date_str


# def stardard_datestring(date_str: str) -> str:
#     return parse_datestring(date_str).strftime("%Y-%m-%d")

if __name__ == "__main__":
    dates = []
    for year_str in [
        "Sep 23, 2024",
        "Oct 23, 1995",
        "Sept 23, 2024",
        "Sept. 25, 2024" , 
        "May 06, 2024",
        "March 20, 1997",
    ]:
        date = parse_datestring(year_str)
        print(date)
        dates.append(date)
    print(max(dates))
