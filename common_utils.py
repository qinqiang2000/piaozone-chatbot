import logging

from settings import CONFIG_PATH
import json


def get_config(assistant_id=None, key=None):
    with open(CONFIG_PATH, "r", encoding="utf-8") as file:
        if not assistant_id:
            # 不传assistant_id则表示获取文档所有json
            return json.load(file)
        if key:
            return json.load(file)[assistant_id][key]
        else:
            return json.load(file)[assistant_id]


def save_config(assistant_id, key, content):
    raw_config = get_config()
    raw_config[assistant_id][key] = content
    with open(CONFIG_PATH, "w", encoding="utf-8") as file:
        json.dump(raw_config, file, indent=4)
    logging.info(f"保存文件config.json {raw_config}")
