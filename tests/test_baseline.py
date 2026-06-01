"""Tests for the baseline annotation model (output parsing; LLM call injected)."""

import importlib
import json
from types import SimpleNamespace

from src.base.model import Annotation, AnnotationModel

# Attempt folders are timestamped (e.g. `20260601_204044_baseline`), so their
# names are not valid Python identifiers and must be loaded via importlib rather
# than a plain `import` statement.
BaselineModel = importlib.import_module(
    "src.attempts.20260601_204044_baseline"
).BaselineModel


def test_baseline_is_an_annotation_model():
    assert isinstance(BaselineModel(completion_fn=lambda **k: None), AnnotationModel)


def _response(content):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


def test_predict_parses_annotation_json_from_llm_output():
    annotations = {
        "variants": ["rs9923231"],
        "title": "A study",
        "summary": "Findings.",
        "var_drug_ann": [{"Variant/Haplotypes": "rs9923231", "Drug(s)": "warfarin"}],
    }
    captured = {}

    def fake_completion(model, messages, **kwargs):
        captured["model"] = model
        captured["prompt"] = messages[0]["content"]
        return _response("Sure!\n" + json.dumps(annotations) + "\nDone.")

    model = BaselineModel(model="provider/m", completion_fn=fake_completion)
    result = model.predict("# Paper about rs9923231 and warfarin")

    assert isinstance(result, Annotation)
    assert result.variants == ["rs9923231"]
    assert result.var_drug_ann == [
        {"Variant/Haplotypes": "rs9923231", "Drug(s)": "warfarin"}
    ]
    assert captured["model"] == "provider/m"
    assert "rs9923231" in captured["prompt"]  # the paper markdown is in the prompt
