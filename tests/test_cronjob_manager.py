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


class TestCronJobManagerErrorPaths:
    """Exercise the error branches the original suite never hits."""

    @patch("services.cronjob_manager.k8s_config.load_incluster_config")
    @patch("services.cronjob_manager.client.BatchV1Api")
    def test_list_cronjobs_propagates_api_exception(
        self, mock_batch_api, mock_load_config
    ):
        from services.cronjob_manager import ApiException, CronJobManager

        mock_api = Mock()
        mock_api.list_namespaced_cron_job.side_effect = ApiException(reason="boom")
        mock_batch_api.return_value = mock_api

        manager = CronJobManager()
        with pytest.raises(ApiException) as exc_info:
            manager.list_cronjobs()
        assert exc_info.type is ApiException
        mock_api.list_namespaced_cron_job.assert_called_once()

    @patch("services.cronjob_manager.k8s_config.load_incluster_config")
    @patch("services.cronjob_manager.client.BatchV1Api")
    def test_list_cronjobs_propagates_generic_exception(
        self, mock_batch_api, mock_load_config
    ):
        from services.cronjob_manager import CronJobManager

        mock_api = Mock()
        mock_api.list_namespaced_cron_job.side_effect = RuntimeError("unexpected")
        mock_batch_api.return_value = mock_api

        manager = CronJobManager()
        with pytest.raises(RuntimeError, match="unexpected") as exc_info:
            manager.list_cronjobs()
        assert "unexpected" in str(exc_info.value)

    @patch("services.cronjob_manager.k8s_config.load_incluster_config")
    @patch("services.cronjob_manager.client.BatchV1Api")
    def test_update_cronjob_propagates_api_exception(
        self, mock_batch_api, mock_load_config
    ):
        from services.cronjob_manager import ApiException, CronJobManager

        mock_api = Mock()
        mock_api.read_namespaced_cron_job.side_effect = ApiException(reason="not found")
        mock_batch_api.return_value = mock_api

        manager = CronJobManager()
        with pytest.raises(ApiException) as exc_info:
            manager.update_cronjob_schedule("missing", "*/10 * * * *")
        assert exc_info.type is ApiException

    @patch("services.cronjob_manager.k8s_config.load_incluster_config")
    @patch("services.cronjob_manager.client.BatchV1Api")
    def test_update_cronjob_propagates_generic_exception(
        self, mock_batch_api, mock_load_config
    ):
        from services.cronjob_manager import CronJobManager

        mock_api = Mock()
        mock_api.read_namespaced_cron_job.side_effect = RuntimeError("server gone")
        mock_batch_api.return_value = mock_api

        manager = CronJobManager()
        with pytest.raises(RuntimeError, match="server gone") as exc_info:
            manager.update_cronjob_schedule("any", "0 * * * *")
        assert "server gone" in str(exc_info.value)

    @patch("services.cronjob_manager.k8s_config.load_incluster_config")
    @patch("services.cronjob_manager.client.BatchV1Api")
    def test_create_job_propagates_api_exception(
        self, mock_batch_api, mock_load_config
    ):
        from services.cronjob_manager import ApiException, CronJobManager

        mock_api = Mock()
        mock_api.read_namespaced_cron_job.side_effect = ApiException(reason="missing")
        mock_batch_api.return_value = mock_api

        manager = CronJobManager()
        with pytest.raises(ApiException) as exc_info:
            manager.create_job_from_cronjob("missing", "1h")
        assert exc_info.type is ApiException

    @patch("services.cronjob_manager.k8s_config.load_incluster_config")
    @patch("services.cronjob_manager.client.BatchV1Api")
    def test_create_job_propagates_generic_exception(
        self, mock_batch_api, mock_load_config
    ):
        from services.cronjob_manager import CronJobManager

        mock_api = Mock()
        mock_api.read_namespaced_cron_job.side_effect = TypeError("bad arg")
        mock_batch_api.return_value = mock_api

        manager = CronJobManager()
        with pytest.raises(TypeError, match="bad arg") as exc_info:
            manager.create_job_from_cronjob("any", "1h")
        assert "bad arg" in str(exc_info.value)


class TestCronJobManagerInit:
    """Cover the in-cluster-config-fail-then-kubeconfig fallback."""

    @patch("services.cronjob_manager.os.path.exists", return_value=True)
    @patch("services.cronjob_manager.k8s_config.load_kube_config")
    @patch(
        "services.cronjob_manager.k8s_config.load_incluster_config",
        side_effect=Exception("not in cluster"),
    )
    @patch("services.cronjob_manager.client.BatchV1Api")
    def test_falls_back_to_kubeconfig_when_in_cluster_fails(
        self, mock_batch_api, mock_in_cluster, mock_kube_cfg, mock_exists
    ):
        from services.cronjob_manager import CronJobManager

        CronJobManager()
        mock_in_cluster.assert_called_once()
        mock_kube_cfg.assert_called_once()

    @patch("services.cronjob_manager.os.path.exists", return_value=False)
    @patch(
        "services.cronjob_manager.k8s_config.load_incluster_config",
        side_effect=Exception("not in cluster"),
    )
    @patch("services.cronjob_manager.client.BatchV1Api")
    def test_warns_when_no_kubeconfig_available(
        self, mock_batch_api, mock_in_cluster, mock_exists
    ):
        # Should NOT raise — just warns and leaves batch_v1 uninitialised for API calls.
        from services.cronjob_manager import CronJobManager

        m = CronJobManager()
        # batch_v1 still constructed (uses the BatchV1Api mock) but config is uninitialised.
        assert m.batch_v1 is not None


class TestCronJobManagerSingleton:
    @patch("services.cronjob_manager.k8s_config.load_incluster_config")
    @patch("services.cronjob_manager.client.BatchV1Api")
    def test_singleton_caches_first_instance(self, mock_batch_api, mock_load_config):
        import services.cronjob_manager as cm

        # Reset the module-level cache so the test is deterministic.
        cm._cronjob_manager = None
        a = cm.get_cronjob_manager()
        b = cm.get_cronjob_manager()
        assert a is b
