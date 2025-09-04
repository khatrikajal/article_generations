import re
import unicodedata

def clean_text(raw: str) -> str:
    """Clean raw scraped text: HTML, links, emails, unicode junk, etc."""
    if not raw:
        return ""

    text = str(raw)

    # --- Step 1: Remove scripts/styles ---
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)

    # --- Step 2: Remove markdown images/links ---
    text = re.sub(r"\[!\[.*?\]\(.*?\)\]\(.*?\)", " ", text)  # linked images
    text = re.sub(r"!\[.*?\]\(.*?\)", " ", text)             # images
    text = re.sub(r"\[([^\]]+)\]\((?:mailto:|http[s]?:\/\/)?[^\)]*\)", r"\1", text)  # links → text

    # --- Step 3: Remove raw URLs / emails ---
    text = re.sub(r"http[s]?:\/\/\S+", " ", text)
    text = re.sub(r"\S+@\S+\.\S+", " ", text)

    # --- Step 4: Remove any remaining HTML tags ---
    text = re.sub(r"<[^>]+>", " ", text)

    # --- Step 5: Normalize unicode ---
    text = unicodedata.normalize("NFKC", text)

    # --- Step 6: Remove junk characters ---
    text = re.sub(r"[^\x00-\x7F]+", " ", text)  # non-ASCII fallback
    text = re.sub(r"[•●■▪]+", " ", text)        # bullets
    text = re.sub(r"[“”«»]", '"', text)
    text = re.sub(r"[‘’]", "'", text)
    text = re.sub(r"[–—]", "-", text)

    # --- Step 7: Collapse whitespace / line breaks ---
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"\s{2,}", " ", text)

    # --- Step 8: Remove duplicate punctuation ---
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r"[,;:]{2,}", ",", text)

    # --- Step 9: Trim ---
    text = text.strip()

    return text
