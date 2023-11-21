import openai
from openai import OpenAI


# 创建一个Assistant类，用于处理openai的请求
class Assistant:
    def __init__(self, assistant_id, api_key=None, base_url=None, ):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.assistant_id = assistant_id
        self.run = None
        self.thread_map = {}   # 不能指定id创建thread，所以需要一个map来存储用户id和thread_id的映射关系

    def chat(self, user_id, content):
        # 如果用户id不存在，创建一个新的thread;
        if user_id not in self.thread_map:
            thread = self.client.beta.threads.create()
            self.thread_map[user_id] = thread.id

        thread_id = self.thread_map.get(user_id)

        self.client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=content
        )

        self.run = self.client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=self.assistant_id
        )

    def get_answer(self, user_id):
        thread_id = self.thread_map.get(user_id)
        if not thread_id:
            return None

        run = self.client.beta.threads.runs.retrieve(
            thread_id=thread_id,
            run_id=self.run.id
        )

        if run.status != "completed":
            return None

        messages = self.client.beta.threads.messages.list(thread_id=thread_id, limit=1)
        return messages.data[0].content[0].text.value
