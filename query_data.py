from collections import defaultdict
from itertools import chain

from langchain.callbacks.base import BaseCallbackManager
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.chains import (
    ConversationalRetrievalChain,
    LLMChain, RetrievalQA
)
from langchain.chains.question_answering import load_qa_chain
from langchain.chat_models import ChatOpenAI, AzureChatOpenAI
from langchain.embeddings import OpenAIEmbeddings
from langchain.memory import ConversationBufferWindowMemory

from prompt import fpy_condense_question_prompt, normal_prompt
import os
from settings import AZURE_BASE_URL, AZURE_DEPLOYMENT_NAME, AZURE_API_KEY, AZURE_EBD_DEPLOYMENT_NAME

session = {}


def feq_sort(*lists):
    counter = defaultdict(int)
    for x in chain(*lists):
        counter[x] += 1
    return [key for (key, value) in
            sorted(counter.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)]


def get_citations(results):
    citations = []
    for r in results:
        title = r.metadata['title']

        # 如果有行数，把行数加到标题后面；因这里的行数是从0开始的，还算上标题行，所以要加2
        if 'row' in r.metadata:
            title = r.metadata['title'] + f"(第{r.metadata['row']+2}行)"

        citations.append(f"[{title}：{r.metadata['url']}]")

    # citations = [f"[{links[u]}：{u}]" for u in urls]
    return ' '.join(citations)


def get_embeddings(api_type=None):
    if api_type == 'azure':
        os.environ["OPENAI_API_TYPE"] = "azure"
        os.environ["OPENAI_API_BASE"] = AZURE_BASE_URL
        os.environ["OPENAI_API_KEY"] = AZURE_API_KEY

        return OpenAIEmbeddings(deployment=AZURE_EBD_DEPLOYMENT_NAME)

    return OpenAIEmbeddings()


def get_chain(retriever, api_type=None):
    if api_type == 'azure':
        model = AzureChatOpenAI(
            openai_api_base=AZURE_BASE_URL,
            openai_api_version="2023-03-15-preview",
            deployment_name=AZURE_DEPLOYMENT_NAME,
            openai_api_key=AZURE_API_KEY,
            openai_api_type="azure",
            streaming=True, callback_manager=BaseCallbackManager([StreamingStdOutCallbackHandler()]),
            verbose=True, temperature=0
        )
    else:
        model = ChatOpenAI(streaming=True, callback_manager=BaseCallbackManager([StreamingStdOutCallbackHandler()]),
                           verbose=True, temperature=0)

    qa = RetrievalQA.from_chain_type(llm=model, chain_type="stuff",
                                     retriever=retriever, return_source_documents=True,
                                     input_key="question", output_key="answer")
    # qa = ConversationalRetrievalChain.from_llm(model, retriever,
    #                                            return_source_documents=True)
    return qa


# 效果不好，待找到原因
def get_chain0(retriever):
    # define two LLM models from OpenAI
    llm = ChatOpenAI(temperature=0)

    streaming_llm = ChatOpenAI(
        streaming=True,
        callback_manager=BaseCallbackManager([
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
def get_chat_model(sid, api_type=None):
    global session

    if sid in session:
        return session[sid]

    if api_type == 'azure':
        llm = AzureChatOpenAI(
            openai_api_base=AZURE_BASE_URL,
            openai_api_version="2023-03-15-preview",
            deployment_name=AZURE_DEPLOYMENT_NAME,
            openai_api_key=AZURE_API_KEY,
            openai_api_type="azure",
            streaming=True, callback_manager=CallbackManager([StreamingStdOutCallbackHandler()]),
            verbose=True, temperature=0
        )
    else:
        llm = ChatOpenAI(temperature=0)

    session[sid] = LLMChain(
        llm=llm,
        prompt=normal_prompt,
        memory=ConversationBufferWindowMemory(k=5),
    )

    return session[sid]
