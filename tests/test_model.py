"""Tests for the AnnotationModel interface and the Annotation data model."""

import pytest

from src.base.model import Annotation, AnnotationModel


def _sample_dict():
    return {
        "variants": ["rs9923231", "rs1057910"],
        "title": "A pharmacogenomics study",
        "summary": "This study investigates ...",
        "study_parameters": [{"Study Type": "cohort", "Study Cases": 124.0}],
        "var_drug_ann": [{"Variant/Haplotypes": "rs9923231", "Drug(s)": "warfarin"}],
        "var_pheno_ann": [{"Variant/Haplotypes": "rs1057910", "Phenotype": "bleeding"}],
        "var_fa_ann": [{"Variant/Haplotypes": "rs1057910", "Assay type": "luciferase"}],
    }


def test_annotation_holds_all_sections():
    ann = Annotation(
        variants=["rs1"],
        title="t",
        summary="s",
        study_parameters=[{"a": 1}],
        var_drug_ann=[{"b": 2}],
        var_pheno_ann=[{"c": 3}],
        var_fa_ann=[{"d": 4}],
    )
    assert ann.variants == ["rs1"]
    assert ann.title == "t"
    assert ann.summary == "s"
    assert ann.study_parameters == [{"a": 1}]
    assert ann.var_drug_ann == [{"b": 2}]
    assert ann.var_pheno_ann == [{"c": 3}]
    assert ann.var_fa_ann == [{"d": 4}]


def test_from_dict_then_to_dict_roundtrips_the_json_shape():
    d = _sample_dict()
    assert Annotation.from_dict(d).to_dict() == d


def test_from_dict_ignores_extra_keys_and_defaults_missing_sections():
    # annotation files also carry a redundant top-level "pmcid"; it is not a
    # modeled section and should be ignored. Missing sections default to empty.
    ann = Annotation.from_dict({"pmcid": "PMC1", "title": "t", "summary": "s"})
    assert ann.title == "t"
    assert ann.variants == []
    assert ann.var_drug_ann == []


def test_annotation_model_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        AnnotationModel()


def test_subclass_must_implement_predict():
    class Incomplete(AnnotationModel):
        pass

    with pytest.raises(TypeError):
        Incomplete()


def test_concrete_subclass_predicts_an_annotation():
    class Dummy(AnnotationModel):
        def predict(self, markdown_content):
            return Annotation.from_dict(_sample_dict())

    result = Dummy().predict("# A paper\nrs9923231 ...")
    assert isinstance(result, Annotation)
    assert result.variants == ["rs9923231", "rs1057910"]
