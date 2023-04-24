from langchain.prompts.prompt import PromptTemplate

condense_template = """给出以下聊天记录和一个后续问题，重新表述后续输入问题，使其成为一个独立的问题；或结束对话，如果它看起来已经完成了.
聊天记录:\"""
{chat_history}
\"""
后续输入: \"""
{question}
\"""
独立的问题:"""

fpy_condense_question_prompt = PromptTemplate.from_template(condense_template)

qa_template = """你是一个提供有用建议的人工智能助手。你得到的是来自发票云知识库的以下摘录部分和一个问题。根据提供的上下文，
提供一个对话式的答案。如果你不知道答案，请回答：“Sorry，找不到合适答案，我用通用知识回答：”，不要试图编造一个答案。
问题: {question}
=========
{context}
=========
用Markdown回答:"""

fpy_qa_prompt = PromptTemplate(
    template=qa_template, input_variables=["context", "question"]
)
