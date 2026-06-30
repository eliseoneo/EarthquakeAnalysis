"""Comparador internacional de perfiles ambientales."""

from __future__ import annotations

from layer_b.models import InternationalComparison


def compare_regions(
    reference_region: str,
    feature_maps: dict[str, dict[str, float]],
    key_features: list[str],
) -> list[InternationalComparison]:
    ref_map = feature_maps.get(reference_region, {})
    if not ref_map:
        return []

    comparisons: list[InternationalComparison] = []
    for region, fmap in feature_maps.items():
        if region == reference_region:
            continue

        matching: list[str] = []
        non_matching: list[str] = []
        scores: list[float] = []

        for feat in key_features:
            rv = ref_map.get(feat)
            ov = fmap.get(feat)
            if rv is None or ov is None:
                continue
            denom = max(abs(rv), abs(ov), 1e-6)
            rel_diff = abs(rv - ov) / denom
            scores.append(max(0.0, 1.0 - rel_diff))
            if rel_diff <= 0.25:
                matching.append(feat)
            else:
                non_matching.append(feat)

        similarity = sum(scores) / len(scores) if scores else 0.0
        evidence = "A" if similarity >= 0.75 else "B" if similarity >= 0.5 else "C"

        comparisons.append(
            InternationalComparison(
                region_code=region,
                reference_region=reference_region,
                similarity_score=round(similarity, 4),
                matching_features=matching,
                non_matching_features=non_matching,
                evidence_level=evidence,
                scientific_notes=(
                    "Correlación exploratoria; no implica causalidad sísmica."
                ),
            )
        )

    comparisons.sort(key=lambda c: c.similarity_score, reverse=True)
    return comparisons
