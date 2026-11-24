from api.engine import GLOSSARY,check_text,parse_english

def test_real_glossary_loaded():
    assert GLOSSARY["stats"]["records"]==315
    assert GLOSSARY["stats"]["forbidden"]==112

def test_parser_example():
    terms=parse_english('Lateral guiding (Verbotene Benennung)"sideguide (Vorzugsbenennung)"Side guide (Verbotene Benennung)')
    assert [(x["text"],x["status"]) for x in terms]==[("Lateral guiding","forbidden"),("sideguide","preferred"),("Side guide","forbidden")]

def test_case_insensitive_replacement_and_boundaries():
    findings=check_text("Install the SIDE GUIDE. A side guidepost is unrelated.",GLOSSARY["terms"])
    assert len(findings)==1
    assert findings[0]["suggested_replacements"]==["sideguide"]

def test_longest_overlap_wins():
    findings=check_text("Inspect the Central lubrication system.",GLOSSARY["terms"])
    assert len(findings)==1
    assert findings[0]["matched_text"]=="Central lubrication system"

