"""
Tests for CronJob manager service.
"""

import os
import sys
from unittest.mock import Mock, patch

import pytest

# Add project root to path (must be before imports)
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)


class TestCronJobManager:
    """Test CronJob manager."""

    @patch("services.cronjob_manager.k8s_config.load_incluster_config")
    @patch("services.cronjob_manager.client.BatchV1Api")
    def test_list_cronjobs_success(self, mock_batch_api, mock_load_config):
        """Test listing CronJobs successfully."""
        from services.cronjob_manager import CronJobManager

        mock_api = Mock()
        mock_batch_api.return_value = mock_api

        # Mock CronJob response
        mock_cronjob = Mock()
        mock_cronjob.metadata.name = "binance-klines-15m-production"
        mock_cronjob.metadata.labels = {"interval": "15m"}
        mock_cronjob.spec.schedule = "*/15 * * * *"
        mock_cronjob.spec.suspend = False
        mock_cronjob.status.last_schedule_time = None
        mock_cronjob.status.active = []

        mock_container = Mock()
        mock_container.args = ["--period=15m"]
        mock_template = Mock()
        mock_template.spec.containers = [mock_container]
        mock_cronjob.spec.job_template.spec.template = mock_template

        mock_response = Mock()
        mock_response.items = [mock_cronjob]
        mock_api.list_namespaced_cron_job.return_value = mock_response

        manager = CronJobManager()
        cronjobs = manager.list_cronjobs()

        assert len(cronjobs) == 1
        assert cronjobs[0]["name"] == "binance-klines-15m-production"
        assert cronjobs[0]["schedule"] == "*/15 * * * *"

    @patch("services.cronjob_manager.k8s_config.load_incluster_config")
    @patch("services.cronjob_manager.client.BatchV1Api")
    def test_update_cronjob_schedule_success(self, mock_batch_api, mock_load_config):
        """Test updating CronJob schedule."""
        from services.cronjob_manager import CronJobManager

        mock_api = Mock()
        mock_batch_api.return_value = mock_api

        # Mock existing CronJob
        mock_cronjob = Mock()
        mock_cronjob.spec.schedule = "*/15 * * * *"
        mock_cronjob.spec.suspend = False
        mock_cronjob.metadata.name = "test-cronjob"
        mock_api.read_namespaced_cron_job.return_value = mock_cronjob

        # Mock updated CronJob
        updated_cronjob = Mock()
        updated_cronjob.spec.schedule = "*/10 * * * *"
        updated_cronjob.spec.suspend = False
        updated_cronjob.metadata.name = "test-cronjob"
        mock_api.patch_namespaced_cron_job.return_value = updated_cronjob

        manager = CronJobManager()
        result = manager.update_cronjob_schedule("test-cronjob", "*/10 * * * *")

        assert result["schedule"] == "*/10 * * * *"
        mock_api.patch_namespaced_cron_job.assert_called_once()

    @patch("services.cronjob_manager.k8s_config.load_incluster_config")
    @patch("services.cronjob_manager.client.BatchV1Api")
    def test_create_job_from_cronjob_success(self, mock_batch_api, mock_load_config):
        """Test creating Job from CronJob template."""
        from services.cronjob_manager import CronJobManager

        mock_api = Mock()
        mock_batch_api.return_value = mock_api

        # Mock CronJob template
        mock_cronjob = Mock()
        mock_container = Mock()
        mock_container.args = ["--period=15m"]
        mock_template = Mock()
        mock_template.spec.containers = [mock_container]
        mock_job_spec = Mock()
        mock_job_spec.template = mock_template
        mock_cronjob.spec.job_template.spec = mock_job_spec
        mock_api.read_namespaced_cron_job.return_value = mock_cronjob

        # Mock created Job
        mock_job = Mock()
        mock_job.metadata.name = "manual-extract-15m-1234567890"
        mock_job.metadata.namespace = "petrosa-apps"
        mock_api.create_namespaced_job.return_value = mock_job

        manager = CronJobManager()
        result = manager.create_job_from_cronjob("test-cronjob", "15m", "BTCUSDT")

        assert result["timeframe"] == "15m"
        assert result["symbol"] == "BTCUSDT"
        mock_api.create_namespaced_job.assert_called_once()
