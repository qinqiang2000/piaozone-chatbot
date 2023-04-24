from langchain import FAISS
from langchain.embeddings import OpenAIEmbeddings
from langchain.chat_models import ChatOpenAI
import os
import logging
from config import OPENAI_API_KEY, FAISS_DB_PATH
from query_data import get_chain, get_citations

os.environ['OPENAI_API_KEY'] = OPENAI_API_KEY


if __name__ == "__main__":
    chat = ChatOpenAI(temperature=0)

    # Load from existing index
    rds = FAISS.load_local(FAISS_DB_PATH, OpenAIEmbeddings())
    retriever = rds.as_retriever()

    chatbot = get_chain(retriever)

    logging.info("loading vectorstore")

    # create a chat history buffer
    chat_history = []
    # gather user input for the first question to kick off the bot
    question = input("您好，我是发票云小助手，请问你有什么问题?")

    # keep the bot running in a loop to simulate a conversation
    while True:
        result = chatbot(
            {"question": question, "chat_history": chat_history}
        )
        # if result["answer"].find("搞不定") != -1:

        print("\n更多详情，请参考：", get_citations(result["source_documents"]), "\n")
        chat_history.append((result["question"], result["answer"]))
        question = input()
