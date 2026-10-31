def slugify(text: str) -> str:
    words = "".join(c if c.isalnum() else " " for c in text.lower()).split()
    return "-".join(words)
