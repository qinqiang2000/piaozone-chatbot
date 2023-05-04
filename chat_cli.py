from langchain import FAISS
from query_data import get_chain, get_citations, get_embeddings

FAISS_DB_PATH = 'db'


if __name__ == "__main__":
    # Load from existing index
    rds = FAISS.load_local(FAISS_DB_PATH, get_embeddings())
    retriever = rds.as_retriever()

    qa = get_chain(retriever)

    # create a chat history buffer
    chat_history = []

    # gather user input for the first question to kick off the bot
    question = input("您好，我是发票云小助手，请问你有什么问题?")

    # keep the bot running in a loop to simulate a conversation
    while True:
        result = qa({"question": question, "chat_history": chat_history})

        print("\n更多详情，请参考：", get_citations(result["source_documents"]), "\n")

        KEYWORDS = ["sorry", "chatgpt", "抱歉"]
        if not any(keyword in result["answer"].lower() for keyword in KEYWORDS):
            chat_history.append((result["question"], result["answer"]))

        question = input()
