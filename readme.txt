各产品负责人提供语雀文档【指定分组】链接和名称后，在本地调用yuque_utils.list_yuque_toc("dn5ehb")（参数传产品资料库id，也就是文档url，第二个横杆内容。
如https://jdpiaozone.yuque.com/nbklz3/dn5ehb/kd7vooa93zb2mkkt，dn5ehb就是参数repo，也就是产品资料库id或slug）函数后的结果中找到对应分类的uuid。
如乐企找到的是
{
	'uuid': 'tATIz14vsbS6c-kw',
	'type': 'TITLE',
	'title': '乐企',
	'url': '',
	'slug': '#',
	'id': '',
	'doc_id': '',
	'level': 0,
	'depth': 1,
	'open_window': 1,
	'visible': 1,
	'prev_uuid': '',
	'sibling_uuid': 'B5Mv-F7nfmC_9dAG',
	'child_uuid': '0lO9D93_5DIx7ymg',
	'parent_uuid': '',
	'_serializer': 'v2.toc_item'
}
取其uuid即可。将上述产品资料库id：dn5ehb，和toc的uuid：tATIz14vsbS6c-kw，以及开发者在GPT Assistant添加对应的Assistant id：asst_G5t60WEtbD9ygU5n2Ol727N6
就可以组成下面config.json的配置。faq.md的uuid数组，在同步语雀文档到assistant后会自动填充。
(在云之家艾特机器人 发送“请同步最新文档到Assistant”命令即可要求同步对应机器人的语雀语料)


配置文件说明：
config.json
{
    #assistant的id，一个id对应一个gpt机器人
    "asst_G5t60WEtbD9ygU5n2Ol727N6": {
        "yuque_relate_and_faq_slug": {
            # key是语雀关联的语料指定分组“/”前是产品资料库id，“/”后是分组的toc uuid
            # 数组里的字符串是faq.md的uuid，在第一次同步语雀文档到assistant后会自动填充
            "dn5ehb/tATIz14vsbS6c-kw": [
                "yprsl4tvf5un19gt"
            ]
        },
        # 上一个faq.md的assistant file id
        "last_faq_file_id": "file-sKs0tDR8o0aFtyS3kqMjAY5I",
        # 上一次普通文件的assistant file id数组
        "last_common_file_ids": [
            "file-RWbbrRGNNYuuE9vSOHIP0nf6",
            "file-lQO1t3FXLFIkiDnqyGYciIK4",
            "file-YKm8Cudx49MwseuCnuvlnkwo",
            "file-wlO2cZ0OD8FXOVJ2GXcex8Q1",
            "file-UUPilhVkzJXd1p0JKcQ9tWI7",
            "file-qyCVEDSbi9kjFc52Lie05qXl",
            "file-OlqXALjUDULyz3yy7mCgD8vk",
            "file-WRCGwADuM3POIblitAe7cqRa",
            "file-fnnunNZrWaJRfhatAwLuSC5G"
        ]
    }
}


yzj_assistant_relate.json
key是群聊机器人的yzj_token，value是gpt assistant的id