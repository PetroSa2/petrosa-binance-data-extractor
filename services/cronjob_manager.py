"""
Kubernetes CronJob manager for data extractor.

Provides functionality to list, update, and manage CronJobs.
"""

import logging
import os
from datetime import datetime
from typing import Any, Optional

try:
    from kubernetes import (
        client,
        config as k8s_config,
    )
    from kubernetes.client.rest import ApiException

    K8S_AVAILABLE = True
except ImportError:
    K8S_AVAILABLE = False

logger = logging.getLogger(__name__)


class CronJobManager:
    """Manages Kubernetes CronJobs for data extraction."""

    def __init__(self):
        """Initialize CronJob manager."""
        if not K8S_AVAILABLE:
            raise ImportError(
                "kubernetes package is required. Install with: pip install kubernetes"
            )

        # Load Kubernetes config
        try:
            k8s_config.load_incluster_config()
            logger.info("Loaded in-cluster Kubernetes config")
        except Exception:
            # Fallback to kubeconfig for local development
            kubeconfig_path = os.getenv("KUBECONFIG", "k8s/kubeconfig.yaml")
            if os.path.exists(kubeconfig_path):
                k8s_config.load_kube_config(config_file=kubeconfig_path)
                logger.info(f"Loaded Kubernetes config from {kubeconfig_path}")
            else:
                logger.warning(
                    "No Kubernetes config found - CronJob operations will fail"
                )

        self.namespace = os.getenv("KUBERNETES_NAMESPACE", "petrosa-apps")
        self.batch_v1 = client.BatchV1Api()

    def list_cronjobs(
        self, label_selector: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """
        List all data extraction CronJobs.

        Args:
            label_selector: Optional label selector (e.g., "app=binance-extractor")

        Returns:
            List of CronJob information dictionaries
        """
        try:
            label_selector = label_selector or "app=binance-extractor"
            cronjobs = self.batch_v1.list_namespaced_cron_job(
                namespace=self.namespace, label_selector=label_selector
            )

            result = []
            for cj in cronjobs.items:
                # Extract timeframe from args or labels
                timeframe = None
                if cj.spec.job_template.spec.template.spec.containers:
                    args = (
                        cj.spec.job_template.spec.template.spec.containers[0].args or []
                    )
                    for arg in args:
                        if arg.startswith("--period="):
                            timeframe = arg.split("=")[1]
                            break

                result.append(
                    {
                        "name": cj.metadata.name,
                        "schedule": cj.spec.schedule,
                        "timeframe": timeframe or cj.metadata.labels.get("interval"),
                        "last_schedule_time": (
                            cj.status.last_schedule_time.isoformat()
                            if cj.status.last_schedule_time
                            else None
                        ),
                        "active_jobs": len(cj.status.active or []),
                        "suspended": cj.spec.suspend or False,
                    }
                )

            return result
        except ApiException as e:
            logger.error(f"Kubernetes API error listing CronJobs: {e}")
            raise
        except Exception as e:
            logger.error(f"Error listing CronJobs: {e}")
            raise

    def update_cronjob_schedule(self, job_name: str, schedule: str) -> dict[str, Any]:
        """
        Update CronJob schedule.

        Args:
            job_name: Name of the CronJob
            schedule: New cron schedule expression

        Returns:
            Updated CronJob information
        """
        try:
            # Get current CronJob
            cron_job = self.batch_v1.read_namespaced_cron_job(
                name=job_name, namespace=self.namespace
            )

            old_schedule = cron_job.spec.schedule
            cron_job.spec.schedule = schedule

            # Update CronJob
            updated = self.batch_v1.patch_namespaced_cron_job(
                name=job_name, namespace=self.namespace, body=cron_job
            )

            logger.info(
                f"Updated {job_name} schedule from {old_schedule} to {schedule}"
            )

            return {
                "name": updated.metadata.name,
                "schedule": updated.spec.schedule,
                "suspended": updated.spec.suspend or False,
            }
        except ApiException as e:
            logger.error(f"Kubernetes API error updating CronJob: {e}")
            raise
        except Exception as e:
            logger.error(f"Error updating CronJob: {e}")
            raise

    def create_job_from_cronjob(
        self, cronjob_name: str, timeframe: str, symbol: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Create a one-time Job from a CronJob template.

        Args:
            cronjob_name: Name of the source CronJob
            timeframe: Extraction timeframe
            symbol: Optional specific symbol to extract

        Returns:
            Created Job information
        """
        try:
            # Get CronJob template
            cron_job = self.batch_v1.read_namespaced_cron_job(
                name=cronjob_name, namespace=self.namespace
            )

            # Create Job from CronJob template
            job = client.V1Job(
                metadata=client.V1ObjectMeta(
                    name=f"manual-extract-{timeframe}-{int(datetime.utcnow().timestamp())}",
                    namespace=self.namespace,
                    labels={
                        "app": "binance-extractor",
                        "component": "manual-extraction",
                        "timeframe": timeframe,
                    },
                ),
                spec=cron_job.spec.job_template.spec,
            )

            # Add symbol argument if specified
            if symbol and job.spec.template.spec.containers:
                container = job.spec.template.spec.containers[0]
                if container.args:
                    container.args.append(f"--symbol={symbol}")

            created = self.batch_v1.create_namespaced_job(
                namespace=self.namespace, body=job
            )

            logger.info(f"Created manual extraction job: {created.metadata.name}")

            return {
                "name": created.metadata.name,
                "namespace": created.metadata.namespace,
                "timeframe": timeframe,
                "symbol": symbol,
            }
        except ApiException as e:
            logger.error(f"Kubernetes API error creating Job: {e}")
            raise
        except Exception as e:
            logger.error(f"Error creating Job: {e}")
            raise


# Global CronJob manager instance
_cronjob_manager: Optional[CronJobManager] = None


def get_cronjob_manager() -> CronJobManager:
    """Get global CronJob manager instance."""
    global _cronjob_manager
    if _cronjob_manager is None:
        _cronjob_manager = CronJobManager()
    return _cronjob_manager
