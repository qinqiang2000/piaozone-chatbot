"""
sync_flow模块，用于串联reader和writer
"""

import logging

import common_utils as utils
import sync.gpt_asst_writer as gw
import sync.yq_reader as yq


# GPT Assistant同步流程
# 同步到yzj_token对应的知识库文档到gpt assistant
def sync_gpt_from_yq(yzj_token):
    # 获取语雀知识库id、分组title和assistant_id
    repo, toc_title,  gpt_assistant_id = utils.get_info_by_yzj_token(yzj_token)
    if not repo or not toc_title or not gpt_assistant_id:
        logging.error(f"同步数据到gpt assistant失败，参数或配置有误: {yzj_token}")
        return False

    # 获取语雀知识库文档
    docs = yq.get_docs(repo, toc_title)
    logging.info(f"获取语雀知识库'{toc_title}'文档成功，文档数量: {len(docs)}")

    # 同步数据到gpt assistant
    ret = gw.sync_data(docs, gpt_assistant_id)

    if ret:
        logging.info(f"同步知识库'{toc_title}'数据到gpt assistant成功: {gpt_assistant_id}")

    return ret


# 同步到yzj_token对应的暂存在本地的知识库文档到gpt assistant（测试用）
def sync_gpt_from_cache(yzj_token):
    # 获取语雀知识库id、分组title和assistant_id
    repo, toc_title,  gpt_assistant_id = utils.get_info_by_yzj_token(yzj_token)
    if not repo or not toc_title or not gpt_assistant_id:
        logging.error(f"同步数据到gpt assistant失败，参数或配置有误: {yzj_token}")
        return False

    # 同步数据到gpt assistant
    ret = gw.sync_cache_data(gpt_assistant_id)

    if ret:
        logging.info(f"同步知识库'{toc_title}'数据到gpt assistant成功: {gpt_assistant_id}")

    return ret

