"""Modelo geoespacial geológico (FCN) basado en docs/foco-geologico.md."""

from geological_model.fcn_model import GeologicalFCNModel
from geological_model.insar_gnss_fetch import fetch_and_replace_insar_gnss_rows
from geological_model.models import GeologicalInputFeatures, GeologicalModelOutput

__all__ = [
    "GeologicalFCNModel",
    "GeologicalInputFeatures",
    "GeologicalModelOutput",
    "fetch_and_replace_insar_gnss_rows",
]
