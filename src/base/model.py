"""Base model interface that every annotation attempt inherits.

An attempt is a subclass of :class:`AnnotationModel` that, given one paper's
markdown, reproduces the structured curation as an :class:`Annotation` matching
the shape in ``src/eval/annotation_bench.jsonl``. See the README for the task
definition.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, fields


@dataclass
class Annotation:
    """The structured annotation for one paper.

    Mirrors the ``annotations`` object in ``annotation_bench.jsonl``. The
    top-level container is typed; the table rows stay as plain ``dict``s because
    the curated field names (e.g. ``"Drug(s)"``, ``"Is/Is Not associated"``) are
    not valid Python identifiers.

    Attributes:
        variants: Variant identifiers discussed in the paper (rsIDs or
            normalized variant strings).
        title: The paper title.
        summary: A free-text summary of the study's pharmacogenomic findings.
        study_parameters: Study-level metadata records.
        var_drug_ann: Variant-drug association records.
        var_pheno_ann: Variant-phenotype association records.
        var_fa_ann: Variant functional-assay association records.
    """

    variants: list[str] = field(default_factory=list)
    title: str = ""
    summary: str = ""
    study_parameters: list[dict] = field(default_factory=list)
    var_drug_ann: list[dict] = field(default_factory=list)
    var_pheno_ann: list[dict] = field(default_factory=list)
    var_fa_ann: list[dict] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "Annotation":
        """Build from a JSON-shaped dict, ignoring keys we don't model."""
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in known})

    def to_dict(self) -> dict:
        """Serialize to the JSON shape used in the benchmark."""
        return {f.name: getattr(self, f.name) for f in fields(self)}


class AnnotationModel(ABC):
    """Base class every attempt inherits.

    The autoresearch harness instantiates a subclass and runs ``predict`` across
    the benchmark so attempts can be scored uniformly.
    """

    @abstractmethod
    def predict(self, markdown_content: str) -> Annotation:
        """Annotate one paper.

        Args:
            markdown_content: The full markdown of a single paper.

        Returns:
            The structured annotation reproduced from the paper.
        """
        ...
