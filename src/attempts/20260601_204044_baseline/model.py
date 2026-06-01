"""Baseline attempt: ask an LLM (via litellm) for the whole annotation in one shot.

This is the starting point the autoresearch loop iterates on. It makes a single
LLM call with the paper markdown and a description of the target schema, then
parses the returned JSON into an :class:`Annotation`.
"""

import json
import re
from dataclasses import dataclass
from typing import Callable

from src.base.model import Annotation, AnnotationModel

PROMPT_TEMPLATE = """You are a pharmacogenomics curator. Read the paper below and \
extract its curated annotations as a single JSON object with these keys:

- "variants": list of variant identifiers discussed (rsIDs or variant strings)
- "title": the paper title
- "summary": a concise summary of the pharmacogenomic findings
- "study_parameters": list of study-level metadata records
- "var_drug_ann": list of variant-drug association records
- "var_pheno_ann": list of variant-phenotype association records
- "var_fa_ann": list of variant functional-assay association records

Each record in the *_ann lists is an object whose fields describe one
association (variant/haplotype, gene, drug(s), phenotype category, significance,
direction of effect, the supporting sentence, etc.). Use null for unknown fields.

Respond with ONLY the JSON object.

PAPER MARKDOWN:
{markdown}
"""


def _parse_annotation_json(text: str) -> Annotation:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in model output: {text[:200]!r}")
    return Annotation.from_dict(json.loads(match.group(0)))


@dataclass
class BaselineModel(AnnotationModel):
    """One-shot LLM annotation model.

    ``completion_fn`` is injectable for testing; by default it lazily resolves to
    ``litellm.completion``.
    """

    model: str = "anthropic/claude-sonnet-4-5"
    completion_fn: Callable | None = None

    def predict(self, markdown_content: str) -> Annotation:
        completion = self.completion_fn
        if completion is None:
            import litellm

            completion = litellm.completion
        prompt = PROMPT_TEMPLATE.format(markdown=markdown_content)
        response = completion(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        return _parse_annotation_json(response.choices[0].message.content)
