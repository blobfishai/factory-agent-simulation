"""FactoryBench-100: an executable Oracle-shaped manufacturing ERP benchmark."""

from .catalog import BENCHMARK_NAME, BENCHMARK_VERSION, build_catalog
from .world import FactoryWorld, seed_database

__all__ = [
    "BENCHMARK_NAME",
    "BENCHMARK_VERSION",
    "FactoryWorld",
    "build_catalog",
    "evaluate_policy",
    "seed_database",
    "verify_episode",
]


def __getattr__(name: str):
    if name in {"evaluate_policy", "verify_episode"}:
        from . import evaluation

        return getattr(evaluation, name)
    raise AttributeError(name)
