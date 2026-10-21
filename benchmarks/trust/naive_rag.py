# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "langchain-core==1.6.12",
#     "langchain-text-splitters==1.1.3",
#     "langchain-ollama==1.1.0",
#     "beautifulsoup4==4.15.0",
#     "fastembed==0.9.0",
#     "onnxruntime==1.31.0",
# ]
# ///
"""The naive RAG baseline of the trust benchmark (EVL-092), built with LangChain.

What a tutorial would build: HTML text through BeautifulSoup, the splitter's default-like
1000/200 chunks, dense-only retrieval, a free-text answer with [n] markers, no verification.
It shares with Soundline what would otherwise blur the comparison: the embedder (with its
query/passage prefixes), k, and the model.

Usage: uv run --script naive_rag.py --corpus DIR [--corpus DIR] --dataset FILE \
    --model qwen3.5:9b --output answers.jsonl
"""

import argparse
import json
import time
from pathlib import Path

from bs4 import BeautifulSoup
from fastembed import TextEmbedding
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_ollama import ChatOllama
from langchain_text_splitters import RecursiveCharacterTextSplitter

# LangChain's classic RAG prompt (hub: rlm/rag-prompt), with [n] citations asked for and a
# fixed abstention sentence, so that abstentions can be counted.
PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "human",
            "You are an assistant for question-answering tasks. Use the following pieces of"
            " retrieved context to answer the question. If you don't know the answer, just"
            " reply: Je ne sais pas. Keep the answer concise, in the language of the question,"
            " and cite the context pieces you use with their number in brackets, like [1].\n"
            "Question: {question}\nContext:\n{context}\nAnswer:",
        )
    ]
)


class FastembedEmbeddings(Embeddings):
    """The embedder Soundline uses, with the model's own query/passage prefixes."""

    def __init__(self, model_name: str) -> None:
        self._model = TextEmbedding(model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._model.passage_embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        return next(iter(self._model.query_embed(text))).tolist()


def load(corpora: list[Path]) -> list[Document]:
    documents: list[Document] = []
    for corpus in corpora:
        for path in sorted(corpus.glob("*.html")):
            text = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser").get_text(" ")
            documents.append(Document(" ".join(text.split()), metadata={"source": path.name}))
    return documents


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, action="append", required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--model", default="qwen3.5:9b")
    parser.add_argument("--embedder", default="intfloat/multilingual-e5-large")
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    store = InMemoryVectorStore(FastembedEmbeddings(args.embedder))
    store.add_documents(splitter.split_documents(load(args.corpus)))
    llm = ChatOllama(model=args.model, temperature=0, reasoning=False)

    with args.output.open("w", encoding="utf-8") as output:
        for line in args.dataset.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            case = json.loads(line)
            started = time.perf_counter()
            chunks = store.similarity_search(case["question"], k=args.k)
            context = "\n\n".join(
                f"[{n}] {chunk.page_content}" for n, chunk in enumerate(chunks, 1)
            )
            message = llm.invoke(PROMPT.invoke({"question": case["question"], "context": context}))
            usage = message.usage_metadata or {"input_tokens": 0, "output_tokens": 0}
            record = {
                "id": case["id"],
                "text": str(message.content),
                "context": [
                    {"source": chunk.metadata["source"], "text": chunk.page_content}
                    for chunk in chunks
                ],
                "latency_ms": (time.perf_counter() - started) * 1000,
                "tokens_in": usage["input_tokens"],
                "tokens_out": usage["output_tokens"],
            }
            output.write(json.dumps(record, ensure_ascii=False) + "\n")
            output.flush()
            print(case["id"], flush=True)


if __name__ == "__main__":
    main()
