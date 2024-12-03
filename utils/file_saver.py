#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@File    :   file_saver.py
@Time    :   2024/10/12 11:24:06
@Author  :   wbzhang
@Version :   1.0
@Desc    :   JSON文件存储、读取与更新
"""

import json

from collections import OrderedDict
from utils.common import parse_datestring
from utils.logger import logger


# speech字典中key的顺序
DEFAULT_KEY_ORDER = [
    "speaker",
    "position",
    "year",
    "date",
    "title",
    "summary",
    "highlights",
    "item_id",
    "href",
    "text_url",
    "api_url",
    "pdf_url",
    "youtube_link",
    "content",
]


def unify_speech_date(dt: dict):
    """统一字典中的日期格式为 %B %d, %Y

    Args:
        dt (dict): 字典信息

    Returns:
        dict: 字典信息
    """
    try:
        date = parse_datestring(dt["date"]).strftime("%B %d, %Y")
        dt["date"] = date
    except Exception as e:
        print(f"{dt} Error: {e}")
        pass
    return dt


def unify_speech_dict(
    dt: dict, order: list = None, necessary_keys: list = None, drop_keys: list = None
):
    """统一speech和speech_info字典中键的顺序

    Args:
        dt (dict): _description_
        order (list, optional): _description_. Defaults to None.
        necessary_keys (list, optional): _description_. Defaults to None.

    Returns:
        _type_: _description_
    """
    if not order:
        order = DEFAULT_KEY_ORDER
    if not necessary_keys:
        necessary_keys = ["speaker", "date", "title"]

    result = {}
    for key in DEFAULT_KEY_ORDER:
        if dt.get(key) or key in necessary_keys:
            result[key] = dt.get(key)
    return result


def update_records(
    records: list[dict],
    new: list[dict],
    tag_fields: list[str] = None,
    sort_field: str = None,
):
    """对records格式的list进行去重
    Args:
        records (list[dict]): list[dict]格式的变量
        tag_field (str): 每个元素的标签元素


    """
    if not tag_fields:
        tag_fields = ["speaker", "date", "title"]
    if not sort_field:
        sort_field = "date"

    try:
        if not records:
            records = []
        if not new or len(new) == 0:
            new = []
        records.extend(new)
        # 使用字典去重，确保每个 field 只出现一次. 第一次的值会被第二次的值覆盖
        unique_data = {}
        for item in records:
            tag = tuple(item.get(field) for field in tag_fields)
            unique_data[tag] = unify_speech_dict(item, necessary_keys=tag_fields)

        # 将去重后的字典转换回列表
        unique_list = list(unique_data.values())

        # 使用 `sorted()` 函数根据 `date` 字段进行升序排序
        if sort_field == "date":
            sorted_records = sorted(
                unique_list, key=lambda x: parse_datestring(x["date"]), reverse=True
            )
        else:
            sorted_records = sorted(
                unique_list, key=lambda x: x[sort_field], reverse=True
            )
        return sorted_records
    except Exception as e:
        msg = f"Records update failed. Error: {repr(e)}"
        logger.warning(msg)
        return records


def update_dict(existed: dict, obj: dict, **kwargs):
    """对<key, records>格式的dict进行更新"""
    try:
        for k, v in obj.items():
            if k in existed:
                existed[k] = update_records(existed[k], v, **kwargs)
                logger.info(f"{k} updated.")
            else:
                existed[k] = update_records(v, {}, **kwargs)
        existed = OrderedDict(sorted(existed.items(), reverse=True))
    except Exception as e:
        msg = "Error {} occurred when update dict.".format(repr(e))
        logger.error(msg)
    return existed


def json_dump(obj, filepath: str):
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Error writing to file: {e}")


def json_load(filepath: str):
    """加载json文件

    Args:
        filepath (str): _description_

    Returns:
        _type_: _description_
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj
    except FileNotFoundError:
        print(f"Error. file {filepath} not found.")
        return None
    except json.JSONDecodeError:
        print(f"Error. file {filepath} is not in valid json format.")
        return None
    except Exception as e:
        print(f"Error load file {filepath}: {e}")
        return None


def json_update(filepath: str, obj, **kwargs):
    """更新已存储的json文件

    Args:
        filepath (str): json文件路径
    """
    # 载入已有文件
    exist_obj = json_load(filepath)
    if isinstance(exist_obj, dict) and isinstance(obj, dict):
        for k, v in obj.items():
            if k in exist_obj:
                exist_obj[k] = update_records(exist_obj[k], v, **kwargs)
                logger.info(f"{k} updated.")
            else:
                exist_obj[k] = v
        exist_obj = sort_speeches_dict(exist_obj, **kwargs)
        json_dump(exist_obj, filepath)
        return exist_obj
    elif isinstance(exist_obj, list) and isinstance(obj, list):
        exist_obj = update_records(exist_obj, obj, **kwargs)
        exist_obj = sort_speeches_records(exist_obj)
        json_dump(exist_obj, filepath)
        return exist_obj
    elif not exist_obj:
        if isinstance(obj, dict):
            obj = sort_speeches_dict(obj)
        elif isinstance(obj, list):
            obj = sort_speeches_records(obj)
        json_dump(obj, filepath)
        msg = "JSON file was not existed. New file {} created.".format(filepath)
        logger.error(msg)
        return obj
    else:
        msg = f"JSON update failed. Unknown object type: {type(exist_obj)}"
        logger.error(msg)
        return None


def sort_speeches_records(
    speeches: list, sort_filed: str = None, required_keys: list = None, **kwargs
):
    if speeches is None or speeches == []:
        return speeches

    if not sort_filed:
        sort_filed = "date"
    if not required_keys:
        required_keys = ["date", "title"]

    try:
        # 先统一日期格式
        result = [
            unify_speech_dict(unify_speech_date(speech), **kwargs)
            for speech in speeches
            if all([speech.get(key) for key in required_keys])
        ]
        # 再排序
        result = sorted(
            result, key=lambda x: parse_datestring(x[sort_filed]), reverse=True
        )
    except Exception as e:
        msg = f"Error occurred when sorting speech records. Error: {repr(e)}"
        logger.error(msg)
        result = speeches
    return result


def sort_speeches_dict(
    speeches_by_year: dict, sort_filed: str = None, required_keys: list = None, **kwargs
):
    """对讲话字典进行排序.

    Args:
        speeches_by_year (dict): _description_
        sort_filed (str, optional): _description_. Defaults to 'date'.

    Returns:
        dict: 降序排序后的讲话稿字典.
    """
    if not sort_filed:
        sort_filed = "date"
    if not required_keys:
        required_keys = ["date", "title"]

    tag_fields = kwargs.get("tag_fields", ['date', 'title'])

    try:
        result = {}
        for year, single_year_speeches in speeches_by_year.items():
            if not year.isdigit():
                continue
            # 使用字典去重，确保每个 field 只出现一次. 第一次的值会被第二次的值覆盖
            unique_data = {}
            for item in single_year_speeches:
                if all([item.get(key) for key in required_keys]):
                    tag = tuple(item.get(field) for field in tag_fields)
                    unique_data[tag] = unify_speech_dict(
                        unify_speech_date(item), necessary_keys=tag_fields
                    )
            # 将去重后的字典转换回列表
            single_year = list(unique_data.values())
            # 按日期降序排序
            result[year] = sorted(
                single_year,
                key=lambda x: parse_datestring(x[sort_filed]),
                reverse=True,
            )
        # 按年降序排序
        result = OrderedDict(sorted(result.items(), key=lambda x: int(x[0]), reverse=True))
    except Exception as e:
        msg = f"Error occurred when sorting speech records. Error: {repr(e)}"
        logger.error(msg)
        result = speeches_by_year
    return result


def test_update_dict():
    existed = {
        "2018": [
            {"a": 1, "b": 2, "c": 3},
            {"a": 3, "b": 6, "c": 9},
            {"a": 4, "b": 8, "c": 12},
        ],
        "2019": [
            {"a": 1, "b": 2, "c": 3},
            {"a": 3, "b": 6, "c": 9},
            {"a": 4, "b": 8, "c": 12},
        ],
    }
    new = {
        "2017": [
            {"a": 11, "b": 22, "c": 63},
            {"a": 31, "b": 16, "c": 89},
            {"a": 41, "b": 18, "c": 912},
        ],
        "2019": [
            {"a": 81, "b": 52, "c": 73},
            {"a": 63, "b": 96, "c": 79},
            {"a": 54, "b": 78, "c": 25},
        ],
    }
    union_dict = update_dict(existed=existed, obj=new)
    print(union_dict)


def test_json_load():
    json_data = json_load(
        "../data/fed_speeches/boston_fed_speeches/boston_fed_speech_infos.json"
    )
    if json_data is not None:
        print(json_data)
        print("Succeed.")


if __name__ == "__main__":
    # test_json_load()
    test_update_dict()
    # sort_speeches_app()
    # drop_duplicates_speech_info_app()
