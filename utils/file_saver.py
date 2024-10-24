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

from utils.logger import logger


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


def records_update(records: list[dict], new: list[dict],
                   tag_fields: list[str] = None, sort_field: str= 'date'):
    """对records格式的list进行去重
    Args:
        records (list[dict]): list[dict]格式的变量
        tag_field (str): 每个元素的标签元素

    
    """
    if not tag_fields:
        tag_fields = ['speaker', 'date', 'title']
    records.extend(new)
    try:
        # 使用字典去重，确保每个 field 只出现一次
        unique_data = {}
        for item in records:
            tag = " ".join([str(item[field]) for field in tag_fields])
            unique_data[tag] = item

        # 将去重后的字典转换回列表
        unique_list = list(unique_data.values())

        # 使用 `sorted()` 函数根据 `date` 字段进行升序排序
        sorted_records = sorted(unique_list, key=lambda x: x[sort_field])
        return sorted_records
    except Exception as e:
        msg = f"Records update failed. Error: {repr(e)}"
        logger.warning(msg)
        return records

def json_update(filepath: str, obj, **kwargs):
    """更新已存储的json文件

    Args:
        filepath (str): _description_
    """
    exist_obj = json_load(filepath)
    if isinstance(exist_obj, dict):
        for k, v in obj.items():
            if k in exist_obj:
                exist_obj[k] = records_update(exist_obj[k], v, **kwargs)
                logger.info(f"{k} updated.")
            else:
                exist_obj[k] = v
        json_dump(exist_obj, filepath)
    elif isinstance(exist_obj, list):
        exist_obj = records_update(exist_obj, obj, **kwargs)
        json_dump(exist_obj, filepath)
    elif not exist_obj:
        json_dump(obj, filepath)
        msg = "JSON file {} created.".format(filepath)
        logger.error(msg)
    else:
        msg = f"JSON update failed. Unknown object type: {type(exist_obj)}"
        logger.error(msg)


def test_json_load():
    json_data = json_load(
        "../data/fed_speeches/boston_fed_speeches/boston_fed_speech_infos.json"
    )
    if json_data is not None:
        print(json_data)
        print("Succeed.")


if __name__ == "__main__":
    test_json_load()
