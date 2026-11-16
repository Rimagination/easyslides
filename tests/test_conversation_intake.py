import copy

from scripts.clarification_gate import build_clarification_request, answer_clarification_request, next_clarification_question
from scripts.user_guide import main


def test_new_deck_asks_route_before_assigning_the_native_default():
    request = build_clarification_request('new_deck')
    first = next_clarification_question(request)
    assert first['question_id'] == 'production_scheme'
    assert first['option_ids'] == ['direct_editable', 'image_full_rebuild']
    assert 'template_id' not in request['decisions']
    request = answer_clarification_request(request, {'production_scheme': 'direct_editable'})
    assert request['decisions']['template_id'] == 'academic_general'
    assert request['template_selection']['source'] == 'project_default'
    assert next_clarification_question(request)['question_id'] == 'theme_palette'


def test_native_default_requires_color_and_source_located_identity_before_production():
    known = dict(production_scheme='direct_editable', presentation_mode='standard',
                 audience='specialists', evidence_scope='selected', story_policy='paper_order')
    request = build_clarification_request('paper_deck', known=known)
    assert request['status'] == 'needs_confirmation'
    request = answer_clarification_request(request, {'theme_palette': 'academic_green'})
    image_question = next_clarification_question(request)
    assert image_question['question_id'] == 'theme_image_source'
    assert image_question['option_ids'] == ['template_assets', 'generate_new']
    assert '生图' in image_question['questions'][0]['options'][1]
    request = answer_clarification_request(request, {'theme_image_source': 'template_assets'})
    inspection = next_clarification_question(request)
    assert inspection['question_id'] == 'presentation_identity'
    assert inspection['status'] == 'needs_material_inspection'
    assert inspection['questions'] == []
    request = answer_clarification_request(request, {
        'presentation_identity': 'brief.docx p1: 生物学；汇报人李明，浙江大学；日期由用户明确省略。'
    }, confirmed_by='inspection:brief.docx:p1')
    assert request['status'] == 'confirmed'


def test_generated_theme_image_is_an_explicit_choice_and_is_not_reasked():
    request = build_clarification_request('paper_deck', known={
        'production_scheme':'direct_editable', 'theme_palette':'academic_green'
    })
    assert next_clarification_question(request)['question_id'] == 'theme_image_source'
    request = answer_clarification_request(request, {'theme_image_source':'generate_new'})
    assert request['decisions']['theme_image_source'] == 'generate_new'
    assert 'theme_image_source' not in request['pending_question_ids']


def test_user_provided_theme_image_skips_the_source_question():
    request = build_clarification_request('paper_deck', known={
        'production_scheme':'direct_editable', 'theme_palette':'academic_green',
        'theme_image_path':'user_selected_topic.png'
    })
    assert request['decisions']['theme_image_source'] == 'user_provided'
    assert 'theme_image_source' not in request['pending_question_ids']


def test_image_route_does_not_inherit_the_native_default():
    request = build_clarification_request('new_deck')
    request = answer_clarification_request(request, {'production_scheme': 'image_full_rebuild'})
    assert 'template_id' not in request['decisions']
    assert 'theme_palette' not in request['pending_question_ids']
    assert next_clarification_question(request)['question_id'] == 'reconstruction_mode'


def test_explicit_template_wins_over_native_default():
    request = build_clarification_request('paper_deck', known={
        'production_scheme': 'direct_editable', 'template_id': 'thu_speech'
    })
    assert request['decisions']['template_id'] == 'thu_speech'
    assert 'theme_palette' not in request['pending_question_ids']
    assert 'presentation_identity' not in request['pending_question_ids']


def test_former_paper_template_name_resolves_to_the_new_general_default():
    request = build_clarification_request('paper_deck', known={
        'production_scheme': 'direct_editable', 'template_id': 'academic_paper_report'
    })
    assert request['decisions']['template_id'] == 'academic_general'
    assert next_clarification_question(request)['question_id'] == 'theme_palette'


def test_classic_pack_remains_an_explicit_choice():
    request = build_clarification_request('paper_deck', known={
        'production_scheme': 'direct_editable', 'template_id': 'academic_classic'
    })
    assert request['decisions']['template_id'] == 'academic_classic'
    assert 'theme_image_source' not in request['pending_question_ids']


def test_existing_approved_request_is_not_reopened_for_new_default():
    from scripts.clarification_gate import validate_clarification_request
    request = build_clarification_request('new_deck', known={
        'production_scheme':'direct_editable', 'template_id':'academic_classic',
        'purpose':'defense', 'audience':'peers', 'story_policy':'restructure',
        'page_budget':'source_adaptive', 'canvas_format':'16:9'
    })
    assert request['status'] == 'confirmed'
    request.pop('native_template_intake')
    request['decisions'].pop('template_id')
    assert validate_clarification_request(request)['status'] == 'pass'
    assert next_clarification_question(request)['status'] == 'ready_for_summary'


def test_guide_defaults_to_dialogue_not_browser(capsys):
    assert main([]) == 0
    output = capsys.readouterr().out
    assert '不打开浏览器' in output and 'index.html' not in output
    main(['--html'])
    assert 'index.html' in capsys.readouterr().out


def test_one_context_question_without_mutation():
    request = build_clarification_request('new_deck', known={
        'production_scheme':'direct_editable', 'template_id':'academic_classic'
    })
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
    request = build_clarification_request('new_deck', known={
        'purpose':'defense','audience':'peers','production_scheme':'direct_editable',
        'theme_palette':'academic_green','presentation_identity':'材料已核实；身份信息用户要求省略。',
        'theme_image_source':'template_assets'
    })
    assert next_clarification_question(request)['question_id'] == 'story_policy'
    assert 'reconstruction_mode' not in request['pending_question_ids']
