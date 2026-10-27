from types import SimpleNamespace
from unittest.mock import Mock
from app.script_llm import ScriptGenerator


def test_retired_fallback_is_bounded_and_other_model_role_is_preserved():
    editor = ScriptGenerator("offline-test")
    assert editor._cfg.primary_model == "gpt-5-mini"
    assert editor._cfg.fallback_model == "gpt-6-luna"
    editor._client = Mock()
    editor._client.responses.create.return_value = SimpleNamespace(status="completed", output_text='{"narration_text":"County crews have finished repairing the bridge on Main Street. Officials say the road has reopened and drivers can use it again. The announcement confirms that traffic can now pass through the area after the work was completed.","on_screen_hook":"Main Street reopens"}')
    editor._run_model_with_retry("gpt-4.1-nano", 15, "Write a factual JSON script")
    options = editor._client.responses.create.call_args.kwargs
    assert options["model"] == "gpt-6-luna"
    assert options["max_output_tokens"] == 2000
    assert options["reasoning"] == {"effort": "none"}
    assert options["store"] is False


def test_observed_missing_detail_narration_is_not_eligible_for_output():
    from app.model_options import replacement_payload_problem
    assert replacement_payload_problem({"headline":"No Schedule Details Provided for NAHS Athletics", "body":"It does not provide a schedule."})
    assert replacement_payload_problem({"narration_text":"The supplied text asks a question but does not include an answer."})
    assert replacement_payload_problem({"headline":"Road reopened", "body":"Main Street reopened."}) is None


def test_actual_luna_response_path_rejects_missing_detail_narration():
    import pytest
    editor=ScriptGenerator("offline-test")
    editor._client=Mock()
    editor._client.responses.create.return_value=SimpleNamespace(status="completed",output_text='{"narration_text":"The supplied text asks a question but does not include the answer.","on_screen_hook":"Interview question"}')
    with pytest.raises(ValueError,match="replacement_model_missing_source_details"):
        editor._run_model_with_retry("gpt-6-luna",15,"Rewrite public facts")
