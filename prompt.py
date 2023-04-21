from langchain.prompts.prompt import PromptTemplate

template = """给出以下聊天记录和一个后续问题，重新表述后续输入问题，使其成为一个独立的问题；或结束对话，如果它看起来已经完成了.
聊天记录:\"""
{chat_history}
\"""
后续输入: \"""
{question}
\"""
独立的问题:"""

fpy_condense_question_prompt = PromptTemplate.from_template(template)

template = """你是一个发票云知识库的AI助理。你利用以下知识库内容来回答最后的问题。如果你不知道答案，请回答：“在发票云知识库未找到相关资料，请联系售后”，不要试图编造一个答案。
知识库:\"""

{context}
\"""
问题:\"""
 {question}
\"""

有用的回答:"""

# qa_prompt = PromptTemplate.from_template(template)
fpy_qa_prompt = PromptTemplate(
    template=template, input_variables=["context", "question"]
)
