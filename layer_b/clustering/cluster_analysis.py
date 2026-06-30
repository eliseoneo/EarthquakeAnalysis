"""Clustering ambiental sobre vectores de features."""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.cluster import DBSCAN, SpectralClustering
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler


def run_clustering(
    feature_matrix: list[list[float]],
    region_labels: list[str],
    methods: list[str],
) -> list[dict[str, Any]]:
    if len(feature_matrix) < 3:
        return []

    X = StandardScaler().fit_transform(np.array(feature_matrix, dtype=float))
    results: list[dict[str, Any]] = []

    if "dbscan" in methods:
        labels = DBSCAN(eps=1.2, min_samples=2).fit_predict(X)
        for region, label in zip(region_labels, labels):
            results.append({
                "region_code": region,
                "method": "dbscan",
                "cluster_id": int(label),
                "evidence_level": "B" if label >= 0 else "C",
            })

    if "gaussian_mixture" in methods and len(feature_matrix) >= 4:
        n_components = min(3, len(feature_matrix) - 1)
        gmm = GaussianMixture(n_components=n_components, random_state=42)
        labels = gmm.fit_predict(X)
        for region, label in zip(region_labels, labels):
            results.append({
                "region_code": region,
                "method": "gaussian_mixture",
                "cluster_id": int(label),
                "evidence_level": "B",
            })

    if "spectral" in methods and len(feature_matrix) >= 4:
        n_clusters = min(3, len(feature_matrix) - 1)
        labels = SpectralClustering(
            n_clusters=n_clusters,
            affinity="nearest_neighbors",
            random_state=42,
        ).fit_predict(X)
        for region, label in zip(region_labels, labels):
            results.append({
                "region_code": region,
                "method": "spectral",
                "cluster_id": int(label),
                "evidence_level": "C",
            })

    return results
