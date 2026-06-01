"""Tests for annotation scoring (pure aggregation + judge output parsing)."""

from src.base.model import Annotation
from types import SimpleNamespace

from src.eval.scoring import (
    SECTIONS,
    SectionScore,
    LiteLLMJudge,
    score_annotation,
    parse_section_score,
    build_judge_prompt,
)


def _full_annotation(**overrides):
    base = dict(
        variants=["rs1"],
        title="t",
        summary="s",
        study_parameters=[{"Study Type": "cohort"}],
        var_drug_ann=[{"Drug(s)": "warfarin"}],
        var_pheno_ann=[{"Phenotype": "bleeding"}],
        var_fa_ann=[{"Assay type": "luciferase"}],
    )
    base.update(overrides)
    return Annotation(**base)


def _equality_judge(name, predicted, ground_truth):
    return SectionScore(
        name=name, score=1.0 if predicted == ground_truth else 0.0, rationale="eq"
    )


def test_score_annotation_judges_every_section():
    ann = _full_annotation()
    result = score_annotation(ann, ann, _equality_judge)
    assert set(result.sections) == set(SECTIONS)
    assert result.overall == 1.0


def test_overall_is_mean_of_section_scores():
    gt = _full_annotation()
    pred = _full_annotation(summary="DIFFERENT")  # exactly one section differs
    result = score_annotation(pred, gt, _equality_judge)
    assert result.sections["summary"].score == 0.0
    assert result.overall == (len(SECTIONS) - 1) / len(SECTIONS)


def test_parse_section_score_extracts_json_even_with_surrounding_text():
    text = (
        'Here is my verdict:\n{"score": 0.75, "rationale": "mostly matches"}\nThanks.'
    )
    score = parse_section_score("summary", text)
    assert score.name == "summary"
    assert score.score == 0.75
    assert score.rationale == "mostly matches"


def test_parse_section_score_clamps_out_of_range_scores():
    assert parse_section_score("variants", '{"score": 1.5}').score == 1.0
    assert parse_section_score("variants", '{"score": -0.2}').score == 0.0


def test_build_judge_prompt_mentions_section_and_both_values():
    prompt = build_judge_prompt("var_drug_ann", [{"Drug(s)": "X"}], [{"Drug(s)": "Y"}])
    assert "var_drug_ann" in prompt
    assert "X" in prompt and "Y" in prompt


def test_litellm_judge_calls_completion_and_parses_response():
    captured = {}

    def fake_completion(model, messages, **kwargs):
        captured["model"] = model
        captured["prompt"] = messages[0]["content"]
        content = '{"score": 0.5, "rationale": "partial"}'
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )

    judge = LiteLLMJudge(model="provider/some-model", completion_fn=fake_completion)
    result = judge("summary", "predicted text", "ground truth text")

    assert captured["model"] == "provider/some-model"
    assert "summary" in captured["prompt"]
    assert result == SectionScore(name="summary", score=0.5, rationale="partial")
