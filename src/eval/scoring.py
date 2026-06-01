"""Scoring for predicted annotations: pure aggregation + an LLM-as-judge.

The judge is *injected* so the aggregation logic (:func:`score_annotation`) is
deterministic and unit-testable without any network calls. The default judge,
:class:`LiteLLMJudge`, routes through ``litellm`` so any provider can be used.
"""

import json
import re
from dataclasses import dataclass
from typing import Callable

from src.base.model import Annotation

# Sections of the annotation that the judge scores. ``title`` is produced by the
# model but not scored on its own (it is reflected in ``summary``).
SECTIONS = [
    "variants",
    "summary",
    "study_parameters",
    "var_drug_ann",
    "var_pheno_ann",
    "var_fa_ann",
]


@dataclass
class SectionScore:
    name: str
    score: float  # in [0, 1]
    rationale: str = ""


@dataclass
class AnnotationScore:
    sections: dict[str, SectionScore]
    overall: float


# A judge takes (section_name, predicted_value, ground_truth_value) and returns
# a SectionScore.
Judge = Callable[[str, object, object], SectionScore]


def score_annotation(
    predicted: Annotation, ground_truth: Annotation, judge: Judge
) -> AnnotationScore:
    """Score a predicted annotation against ground truth, section by section.

    The overall score is the mean of the per-section scores.
    """
    sections: dict[str, SectionScore] = {}
    for name in SECTIONS:
        sections[name] = judge(
            name, getattr(predicted, name), getattr(ground_truth, name)
        )
    overall = sum(s.score for s in sections.values()) / len(sections)
    return AnnotationScore(sections=sections, overall=overall)


def build_judge_prompt(section_name: str, predicted, ground_truth) -> str:
    """Build the prompt asking the judge to score one section."""
    return (
        "You are scoring an automated system that reproduces curated "
        "pharmacogenomics annotations from a scientific paper.\n\n"
        f"Section being scored: {section_name}\n\n"
        "Compare the PREDICTED value against the GROUND TRUTH value. Judge how "
        "well the prediction captures the same associations/information as the "
        "ground truth: reward recall of the ground-truth content and penalize "
        "spurious or incorrect content. Ignore differences in ordering, "
        "formatting, and null/empty optional fields.\n\n"
        f"GROUND TRUTH:\n{json.dumps(ground_truth, ensure_ascii=False, indent=2, default=str)}\n\n"
        f"PREDICTED:\n{json.dumps(predicted, ensure_ascii=False, indent=2, default=str)}\n\n"
        'Respond with ONLY a JSON object: {"score": <float 0..1>, "rationale": '
        '"<one sentence>"}'
    )


def parse_section_score(section_name: str, text: str) -> SectionScore:
    """Parse a judge response into a SectionScore, clamping score to [0, 1]."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in judge response: {text!r}")
    data = json.loads(match.group(0))
    score = float(data.get("score", 0.0))
    score = max(0.0, min(1.0, score))
    return SectionScore(
        name=section_name, score=score, rationale=str(data.get("rationale", ""))
    )


@dataclass
class LiteLLMJudge:
    """Default judge: scores a section via an LLM through litellm.

    ``completion_fn`` is injectable for testing; by default it lazily resolves to
    ``litellm.completion`` (so importing this module does not require litellm).
    """

    model: str = "anthropic/claude-sonnet-4-5"
    completion_fn: Callable | None = None

    def __call__(self, section_name: str, predicted, ground_truth) -> SectionScore:
        completion = self.completion_fn
        if completion is None:
            import litellm

            completion = litellm.completion
        prompt = build_judge_prompt(section_name, predicted, ground_truth)
        response = completion(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        text = response.choices[0].message.content
        return parse_section_score(section_name, text)
