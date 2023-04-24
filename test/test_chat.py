import os

from langchain import OpenAI, ConversationChain, LLMChain, PromptTemplate
from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferWindowMemory

from config import OPENAI_API_KEY

os.environ['OPENAI_API_KEY'] = OPENAI_API_KEY


template = """Assistant is a powerful tool that can help with a wide range of tasks and provide valuable insights and 
information on a wide range of topics. Whether you need help with a specific question or just want to have a 
conversation about a particular topic, Assistant is here to assist.
{history}
Human: {human_input}
Assistant:"""

prompt = PromptTemplate(
    input_variables=["history", "human_input"],
    template=template
)


chatgpt_chain = LLMChain(
    llm=ChatOpenAI(temperature=0),
    prompt=prompt,
    memory=ConversationBufferWindowMemory(k=2),
)


if __name__ == "__main__":
    while True:
        human_input = input("Human: ")
        output = chatgpt_chain.predict(human_input=human_input)
        print("Assistant:", output)


# output = chatgpt_chain.predict(human_input="ls ~")
# print(output)
#
# output = chatgpt_chain.predict(human_input="cd ~")
# print(output)