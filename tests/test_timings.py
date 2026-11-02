from bookorbit_tts.audio import AudioData, concat
from bookorbit_tts.timings import WordTiming, timings_from_alignments, timings_from_duration


def test_alignments_follow_piper_word_gaps():
    # 100 Hz so sample counts are hundredths of a second.
    alignments = [
        ("^", 10),
        ("h", 20),
        ("i", 20),
        (" ", 10),
        ("y", 30),
        ("o", 30),
        ("$", 10),
    ]
    words = timings_from_alignments("Hi you", alignments, 100)
    assert [word.word for word in words] == ["Hi", "you"]
    assert words[0].start == 0
    assert words[0].end == 0.5
    assert words[1].start == 0.6
    assert words[1].end == 1.3


def test_a_mismatched_alignment_falls_back_to_word_length():
    words = timings_from_alignments("Hi you", [("h", 100)], 100)
    assert [word.word for word in words] == ["Hi", "you"]
    assert words[0].start == 0
    assert words[-1].end == 1


def test_duration_split_covers_the_clip():
    words = timings_from_duration("one two", 1.0)
    assert words[0] == WordTiming("one", 0.0, 0.5)
    assert words[1].end == 1.0


def test_concat_keeps_word_times_across_the_gap():
    first = AudioData(b"\x00\x00" * 16000, 16000, (WordTiming("one", 0.0, 1.0),))
    second = AudioData(b"\x00\x00" * 16000, 16000, (WordTiming("two", 0.0, 1.0),))
    joined = concat([first, second], gap_ms=120)
    assert joined.words[1].start == 1.12
    assert joined.words[1].end == 2.12
