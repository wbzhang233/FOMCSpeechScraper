import json


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



def test_json_load():
    json_data = json_load(
        "../data/fed_speeches/boston_fed_speeches/boston_fed_speech_infos.json"
    )
    if json_data is not None:
        print(json_data)
        print('Succeed.')


if __name__ == "__main__":
    test_json_load()
