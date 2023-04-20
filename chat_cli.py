from langchain import FAISS
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores.redis import Redis

from prompt import fpy_condense_question_prompt, fpy_qa_prompt
import os
from config import OPENAI_API_KEY, REDIS_URL, INDEX_NAME, FAISS_DB_PATH
from query_data import get_chain, get_citations

os.environ['OPENAI_API_KEY'] = OPENAI_API_KEY


if __name__ == "__main__":
    # Load from existing index
    rds = FAISS.load_local(FAISS_DB_PATH, OpenAIEmbeddings())
    retriever = rds.as_retriever()

    chatbot = get_chain(retriever)

    # create a chat history buffer
    chat_history = []
    # gather user input for the first question to kick off the bot
    question = input("您好，我是发票云小助手，请问你有什么问题?")

    # keep the bot running in a loop to simulate a conversation
    while True:
        result = chatbot(
            {"question": question, "chat_history": chat_history}
        )
        # print(result["answer"])
        print("\n更多详情，请参考：", get_citations(result["source_documents"]), "\n")
        chat_history.append((result["question"], result["answer"]))
        question = input()
