import copy

from scripts.clarification_gate import build_clarification_request, answer_clarification_request, next_clarification_question
from scripts.user_guide import main


def test_guide_defaults_to_dialogue_not_browser(capsys):
    assert main([]) == 0
    output = capsys.readouterr().out
    assert '不打开浏览器' in output and 'index.html' not in output
    main(['--html'])
    assert 'index.html' in capsys.readouterr().out


def test_one_context_question_without_mutation():
    request = build_clarification_request('new_deck')
    before = copy.deepcopy(request)
    next_q = next_clarification_question(request)
    assert next_q['question_id'] == 'purpose' and len(next_q['questions']) == 1
    assert request == before
    request = answer_clarification_request(request, {'purpose':'defense'})
    assert next_clarification_question(request)['question_id'] == 'audience'


def test_image_answer_drives_followup_and_stops_when_clear():
    request = build_clarification_request('image_reconstruction')
    assert next_clarification_question(request)['question_id'] == 'production_scheme'
    request = answer_clarification_request(request, {'production_scheme':'image_full_rebuild'})
    question = next_clarification_question(request)
    assert question['question_id'] == 'reconstruction_mode'
    assert all('Token' in text and '耗时' in text for text in question['questions'][0]['options'])
    request = answer_clarification_request(request, {'reconstruction_mode':'preserve_complex_images'})
    assert next_clarification_question(request)['questions'] == []
    assert next_clarification_question(request)['status'] == 'ready_for_summary'


def test_explicit_choices_are_not_reasked():
    request = build_clarification_request('new_deck', known={'purpose':'defense','audience':'peers','production_scheme':'direct_editable'})
    assert next_clarification_question(request)['question_id'] == 'story_policy'
    assert 'reconstruction_mode' not in request['pending_question_ids']
