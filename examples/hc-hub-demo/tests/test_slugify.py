from textkit import slugify


def test_slugify_joins_words_with_hyphen() -> None:
    assert slugify("Hello, World!") == "hello-world"


def test_slugify_collapses_separators() -> None:
    assert slugify("  a -- b  ") == "a-b"
