"""data-extractor subsystem evaluator (P2.7, petrosa_k8s#697 AC2 / #259).

Adopts the shared `petrosa_otel.evaluators` framework (P2.1) so the
data-extractor service publishes a structured health verdict on
``evaluator.data-extractor.verdict``, closing the last of the five
"silent service" gaps that keep FR17 / FR23 / FR32 at YELLOW.

The evaluator lives in the long-lived API pod (api/main.py FastAPI lifespan)
rather than in the short-lived CronJob entrypoints — it subscribes to the
existing ``binance.extraction.>`` NATS completion stream so the framework's
hysteresis / cadence model (which assumes a long-lived process) works as
designed. See the module docstring in ``health_evaluator.py`` for details.
"""

from evaluators.health_evaluator import (
    DataExtractorHealthEvaluator,
    build_data_extractor_health_evaluator,
)

__all__ = [
    "DataExtractorHealthEvaluator",
    "build_data_extractor_health_evaluator",
]
