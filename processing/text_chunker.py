"""
Splits a document's plain-text paragraphs into chunks for document_chunks.

Chunking rule (deliberately simple for the MVP): one chunk per paragraph,
except very short fragments (headings, stray labels) get merged forward
into the next paragraph instead of becoming their own low-value chunk.
"""

MIN_WORDS_STANDALONE = 5


def chunk_paragraphs(paragraphs: list[str]) -> list[str]:
    """
    paragraphs: list of paragraph strings, in document order (already
    filtered for blank/whitespace-only entries upstream).

    Returns: list of chunk strings, same order, short fragments merged
    forward into the following paragraph.
    """
    chunks = []
    pending = ""

    for para in paragraphs:
        text = para.strip()
        if not text:
            continue

        if pending:
            text = f"{pending} {text}"
            pending = ""

        word_count = len(text.split())
        if word_count < MIN_WORDS_STANDALONE:
            # too short to stand alone — carry forward to merge with the next one
            pending = text
            continue

        chunks.append(text)

    # if the document ends on a short fragment with nothing left to merge into,
    # keep it rather than silently dropping it
    if pending:
        chunks.append(pending)

    return chunks
