from bookorbit_tts.text import normalize, split_for_synthesis


def test_normalize_collapses_whitespace():
    assert normalize("  hello\n\nworld\t!  ") == "hello world !"


def test_short_text_is_one_chunk():
    assert split_for_synthesis("A short sentence.") == ["A short sentence."]


def test_sentences_are_grouped_under_the_limit():
    text = "One sentence here. Two sentences here. Three sentences here."
    chunks = split_for_synthesis(text, max_chars=40)
    assert len(chunks) >= 2
    assert all(len(chunk) <= 40 for chunk in chunks)
    assert " ".join(chunks).split() == text.split()


def test_long_sentence_is_hard_wrapped():
    text = "word " * 200
    chunks = split_for_synthesis(text.strip(), max_chars=50)
    assert all(len(chunk) <= 50 for chunk in chunks)
    assert len(chunks) > 1


def test_empty_text():
    assert split_for_synthesis("   ") == []


def test_a_long_token_cannot_skip_the_chunk_limit():
    chunks = split_for_synthesis("a" * 100, max_chars=40)
    assert chunks
    assert all(len(chunk) <= 40 for chunk in chunks)
    assert "".join(chunks) == "a" * 100
