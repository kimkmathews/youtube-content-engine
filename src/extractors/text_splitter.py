from typing import List
from langchain_text_splitters import RecursiveCharacterTextSplitter

class TextSplitterService:
    def __init__(self, chunk_size: int = 4000, chunk_overlap: int = 500):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            is_separator_regex=False,
        )

    def split_text(self, text: str) -> List[str]:
        if not text:
            return []
        chunks = self.splitter.split_text(text)
        return chunks
