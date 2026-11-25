from build import brief_section_modifier

def test_take_heading_gets_opinion_style():
    assert brief_section_modifier("J Gonzales's take", "<p>x</p>") == " brief-block--take"
    assert brief_section_modifier("J Gonzales\u2019s take", "<p>x</p>") == " brief-block--take"

def test_news_heading_with_word_take_is_not_opinion():
    assert brief_section_modifier("Rent help, take two", "<p>x</p>") == ""
    assert brief_section_modifier("Mistakes in the budget", "<p>x</p>") == ""
