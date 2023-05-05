from langchain.prompts.prompt import PromptTemplate

condense_template = """Given the following conversation and a follow up question, rephrase the follow up question to be a chinese standalone question.

Chat History:
{chat_history}
Follow Up Input: {question}
Standalone question:"""

fpy_condense_question_prompt = PromptTemplate.from_template(condense_template)

qa_template = """你是一个提供有用建议的人工智能助手。你得到的是来自发票云知识库的以下摘录部分和一个问题。根据提供的上下文，
提供一个对话式的答案。如果你不知道答案，请回答：“Sorry，发票云知识库找不到合适答案。我会补充来自ChatGPT的回应...”，不要试图编造一个答案。
问题: {question}
=========
{context}
=========
用Markdown回答:"""

fpy_qa_prompt = PromptTemplate(
    template=qa_template, input_variables=["context", "question"]
)


template = """Assistant is a powerful tool that can help with a wide range of tasks and provide valuable insights and 
information on a wide range of topics. Whether you need help with a specific question or just want to have a 
conversation about a particular topic, Assistant is here to assist.
{history}
Human: {human_input}
Assistant:"""

normal_prompt = PromptTemplate(
    input_variables=["history", "human_input"],
    template=template
)