from collections import defaultdict
from itertools import chain

from langchain.callbacks.base import CallbackManager
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.chains import (
    ConversationalRetrievalChain,
    LLMChain
)
from langchain.chains.question_answering import load_qa_chain
from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferWindowMemory

from prompt import fpy_condense_question_prompt, fpy_qa_prompt, normal_prompt
import os
from config import OPENAI_API_KEY

os.environ['OPENAI_API_KEY'] = OPENAI_API_KEY


def feq_sort(*lists):
    counter = defaultdict(int)
    for x in chain(*lists):
        counter[x] += 1
    return [key for (key, value) in
            sorted(counter.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)]


def get_citations(results):
    links = {}
    urls = []
    for r in results:
        urls.append(r.metadata['url'])
        links[r.metadata['url']] = r.metadata['title']

    citations = [f"[{links[u]}：{u}]" for u in feq_sort(urls)]
    return ' '.join(citations)


def get_chain(retriever):
    chat = ChatOpenAI(streaming=True, callback_manager=CallbackManager([StreamingStdOutCallbackHandler()]),
                      verbose=True, temperature=0)
    qa = ConversationalRetrievalChain.from_llm(chat, retriever, condense_question_prompt=fpy_condense_question_prompt,
                                               return_source_documents=True)
    return qa


# 效果不好，待找到原因
def get_chain0(retriever):
    # define two LLM models from OpenAI
    llm = ChatOpenAI(temperature=0)

    streaming_llm = ChatOpenAI(
        streaming=True,
        callback_manager=CallbackManager([
            StreamingStdOutCallbackHandler()
        ]),
        verbose=True,
        temperature=0
    )

    # use the LLM Chain to create a question creation chain
    question_generator = LLMChain(
        llm=llm,
        prompt=fpy_condense_question_prompt
    )

    # use the streaming LLM to create a question answering chain
    doc_chain = load_qa_chain(
        llm=streaming_llm,
        chain_type="stuff",
        # prompt=fpy_qa_prompt
        prompt=None
    )

    return ConversationalRetrievalChain(
        retriever=retriever,
        combine_docs_chain=doc_chain,
        question_generator=question_generator,
        return_source_documents=True
    )


# 纯粹聊天
session = {}
def get_chat_model(sid):
    global session

    if sid in session:
        return session[sid]

    llm = ChatOpenAI(temperature=0)

    session[sid] = LLMChain(
        llm=llm,
        prompt=normal_prompt,
        memory=ConversationBufferWindowMemory(k=2),
    )

    return session[sid]
