# Klines Retention

Klines retention is owned and executed by the data-manager service. See
[`data_manager/maintenance/klines_retention.py`](https://github.com/PetroSa2/petrosa-data-manager/blob/main/data_manager/maintenance/klines_retention.py)
and its [retention documentation](https://github.com/PetroSa2/petrosa-data-manager/blob/main/docs/klines-retention.md).

This repository no longer contains a retention job or its tests. The direct
MySQL adapter remains here for the klines gap-filler until
[petrosa_k8s#1065](https://github.com/PetroSa2/petrosa_k8s/issues/1065)
switches that workload to the data-manager gateway.
