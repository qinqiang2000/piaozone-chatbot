
配置文件说明：
config.json
{
    #assistant的id
    "asst_G5t60WEtbD9ygU5n2Ol727N6": {
        "yuque_relate_and_faq_slug": {
            # key是语雀关联的语料指定分组“/”前是产品资料库id，“/”后是分组的toc uuid
            # 数组里的字符串是faq.md的uuid
            "sszola/AJ1v7qG6jrUVPEQi": [
            ]
        },
        # 上一个faq.md的assistant file id
        "last_faq_file_id": "file-Fa0qWrolxoetUmyyWck0bUjr",
        # 上一次普通文件的assistant file id数组
        "last_common_file_ids": [
            "file-YKXdCD7teq3AwFX6bMLMrdXc",
            "file-ku2QBhoDV12L2QWDKoTpcKit",
            "file-tCuMkEj7BSY7qMuuN3tjHX1H",
            "file-QXJnUvXg37sVefWAZF2hku3t",
            "file-RfzAGBAhA39379XNGLYEp9iZ",
            "file-dSXLWgnxJ9nTBRuceY6bbnkb",
            "file-fokkdmaAVhUXzwkgQBPwWKKO",
            "file-eacZIU96t9baTg7p1aEZlu6l",
            "file-Ttu7hdGxn7DHBbrLtCeQzb32"
        ]
    }
}


yzj_assistant_relate.json
key是群聊机器人的yzj_token，value是gpt assistant的id