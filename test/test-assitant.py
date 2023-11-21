import time

from assistant import Assistant
from dotenv import load_dotenv

load_dotenv(override=True)


thread_id = 'fpy-abc'

# 创建一个Assistant类，用于处理openai的请求
yzj = Assistant('asst_G5t60WEtbD9ygU5n2Ol727N6')

yzj.chat(thread_id, "怎么申请乐企？")

while True:
    time.sleep(2)
    answer = yzj.get_answer('fpy-abc')
    if answer:
        print(answer)
        break

yzj.chat('fpy-abc', "它的网址是什么？")

while True:
    time.sleep(2)
    answer = yzj.get_answer('fpy-abc')
    if answer:
        print(answer)
        break