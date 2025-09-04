def recursive_chunk_text(text, max_chunk_size=1500):
    """
    Recursively split text into smaller chunks until each
    chunk fits within max_chunk_size characters.
    """
    if len(text) <= max_chunk_size:
        return [text]

    words = text.split()
    chunks, current = [], []

    for word in words:
        if sum(len(w) + 1 for w in current) + len(word) + 1 > max_chunk_size:
            chunks.append(" ".join(current))
            current = []
        current.append(word)

    if current:
        chunks.append(" ".join(current))

    # If any chunk is still too large → recurse further
    final_chunks = []
    for chunk in chunks:
        if len(chunk) > max_chunk_size:
            final_chunks.extend(recursive_chunk_text(chunk, max_chunk_size))
        else:
            final_chunks.append(chunk)

    return final_chunks
