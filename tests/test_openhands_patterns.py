"""
Test Mockernetes with OpenHands runtime-api usage patterns.

These tests verify that Mockernetes works correctly with the specific
patterns used by the OpenHands runtime-api project.
"""

import pytest
from kubernetes import client as k8s_client
from kubernetes.client.rest import ApiException

from mockernetes import mock_kubernetes


def test_runtime_creation_pattern():
    """Test the full runtime creation pattern from OpenHands."""
    with mock_kubernetes() as mock_k8s:
        # Simulate the OpenHands runtime creation process
        runtime_id = "test-runtime-123"
        session_id = "session-456"
        api_key_name = "test-api-key"
        namespace = "default"

        # Get API clients (as done in OpenHands k8s.py)
        core_api = k8s_client.CoreV1Api()
        apps_api = k8s_client.AppsV1Api()
        networking_api = k8s_client.NetworkingV1Api()
        policy_api = k8s_client.PolicyV1Api()

        # 1. Create ServiceAccount
        sa_manifest = k8s_client.V1ServiceAccount(
            metadata=k8s_client.V1ObjectMeta(
                name=f"runtime-{runtime_id}",
                labels={"runtime_id": runtime_id, "session_id": session_id},
                annotations={"api_key_name": api_key_name},
            )
        )

        created_sa = core_api.create_namespaced_service_account(
            namespace=namespace, body=sa_manifest
        )
        assert created_sa.metadata.name == f"runtime-{runtime_id}"

        # 2. Create Deployment
        deployment_manifest = k8s_client.V1Deployment(
            metadata=k8s_client.V1ObjectMeta(
                name=f"runtime-{runtime_id}",
                labels={"runtime_id": runtime_id, "session_id": session_id},
            ),
            spec=k8s_client.V1DeploymentSpec(
                replicas=1,
                selector=k8s_client.V1LabelSelector(
                    match_labels={"runtime_id": runtime_id}
                ),
                template=k8s_client.V1PodTemplateSpec(
                    metadata=k8s_client.V1ObjectMeta(
                        labels={"runtime_id": runtime_id, "session_id": session_id}
                    ),
                    spec=k8s_client.V1PodSpec(
                        service_account_name=f"runtime-{runtime_id}",
                        containers=[
                            k8s_client.V1Container(
                                name="runtime",
                                image="ghcr.io/all-hands-ai/runtime:latest",
                                command=["/bin/bash"],
                                args=["-c", "sleep infinity"],
                                env=[
                                    k8s_client.V1EnvVar(
                                        name="RUNTIME_ID", value=runtime_id
                                    ),
                                    k8s_client.V1EnvVar(
                                        name="SESSION_API_KEY", value="test-key"
                                    ),
                                ],
                                resources=k8s_client.V1ResourceRequirements(
                                    requests={"cpu": "100m", "memory": "512Mi"},
                                    limits={"cpu": "1000m", "memory": "2Gi"},
                                ),
                            )
                        ],
                    ),
                ),
            ),
        )

        created_deployment = apps_api.create_namespaced_deployment(
            namespace=namespace, body=deployment_manifest
        )
        assert created_deployment.metadata.name == f"runtime-{runtime_id}"

        # 3. Set up owner references (as done in OpenHands)
        owner_reference = k8s_client.V1OwnerReference(
            api_version="apps/v1",
            kind="Deployment",
            name=created_deployment.metadata.name,
            uid=created_deployment.metadata.uid,
        )

        # 4. Create Service with owner reference
        service_manifest = k8s_client.V1Service(
            metadata=k8s_client.V1ObjectMeta(
                name=f"runtime-{runtime_id}",
                labels={"runtime_id": runtime_id},
                owner_references=[owner_reference],
            ),
            spec=k8s_client.V1ServiceSpec(
                selector={"runtime_id": runtime_id},
                ports=[
                    k8s_client.V1ServicePort(name="ssh", port=2222, target_port=2222),
                    k8s_client.V1ServicePort(
                        name="vscode", port=8000, target_port=8000
                    ),
                    k8s_client.V1ServicePort(
                        name="work1", port=12000, target_port=12000
                    ),
                    k8s_client.V1ServicePort(
                        name="work2", port=12001, target_port=12001
                    ),
                ],
            ),
        )

        created_service = core_api.create_namespaced_service(
            namespace=namespace, body=service_manifest
        )
        assert created_service.metadata.name == f"runtime-{runtime_id}"

        # 5. Create PVC with owner reference
        pvc_manifest = k8s_client.V1PersistentVolumeClaim(
            metadata=k8s_client.V1ObjectMeta(
                name=f"runtime-{runtime_id}",
                labels={"runtime_id": runtime_id},
                owner_references=[owner_reference],
            ),
            spec=k8s_client.V1PersistentVolumeClaimSpec(
                access_modes=["ReadWriteOnce"],
                resources=k8s_client.V1ResourceRequirements(
                    requests={"storage": "10Gi"}
                ),
            ),
        )

        created_pvc = core_api.create_namespaced_persistent_volume_claim(
            namespace=namespace, body=pvc_manifest
        )
        assert created_pvc.metadata.name == f"runtime-{runtime_id}"
        assert created_pvc.status.phase == "Bound"  # Should be simulated as bound

        # 6. Create PodDisruptionBudget
        pdb_manifest = k8s_client.V1PodDisruptionBudget(
            metadata=k8s_client.V1ObjectMeta(
                name=f"runtime-{runtime_id}",
                labels={"runtime_id": runtime_id},
                owner_references=[owner_reference],
            ),
            spec=k8s_client.V1PodDisruptionBudgetSpec(
                min_available=1,
                selector=k8s_client.V1LabelSelector(
                    match_labels={"runtime_id": runtime_id}
                ),
            ),
        )

        created_pdb = policy_api.create_namespaced_pod_disruption_budget(
            namespace=namespace, body=pdb_manifest
        )
        assert created_pdb.metadata.name == f"runtime-{runtime_id}"

        # 7. Create Ingress
        ingress_manifest = k8s_client.V1Ingress(
            metadata=k8s_client.V1ObjectMeta(
                name=f"runtime-{runtime_id}",
                labels={"runtime_id": runtime_id},
                owner_references=[owner_reference],
                annotations={
                    "nginx.ingress.kubernetes.io/rewrite-target": "/",
                    "nginx.ingress.kubernetes.io/ssl-redirect": "true",
                },
            ),
            spec=k8s_client.V1IngressSpec(
                rules=[
                    k8s_client.V1IngressRule(
                        host=f"{runtime_id}.example.com",
                        http=k8s_client.V1HTTPIngressRuleValue(
                            paths=[
                                k8s_client.V1HTTPIngressPath(
                                    path="/",
                                    path_type="Prefix",
                                    backend=k8s_client.V1IngressBackend(
                                        service=k8s_client.V1IngressServiceBackend(
                                            name=f"runtime-{runtime_id}",
                                            port=k8s_client.V1ServiceBackendPort(
                                                number=8000
                                            ),
                                        )
                                    ),
                                )
                            ]
                        ),
                    )
                ]
            ),
        )

        created_ingress = networking_api.create_namespaced_ingress(
            namespace=namespace, body=ingress_manifest
        )
        assert created_ingress.metadata.name == f"runtime-{runtime_id}"


def test_pod_status_monitoring_pattern():
    """Test the pod status monitoring pattern from OpenHands."""
    with mock_kubernetes() as mock_k8s:
        runtime_id = "test-runtime-456"
        namespace = "default"

        core_api = k8s_client.CoreV1Api()
        apps_api = k8s_client.AppsV1Api()

        # Create deployment (which creates pods)
        deployment = k8s_client.V1Deployment(
            metadata=k8s_client.V1ObjectMeta(
                name=f"runtime-{runtime_id}", labels={"runtime_id": runtime_id}
            ),
            spec=k8s_client.V1DeploymentSpec(
                replicas=1,
                selector=k8s_client.V1LabelSelector(
                    match_labels={"runtime_id": runtime_id}
                ),
                template=k8s_client.V1PodTemplateSpec(
                    metadata=k8s_client.V1ObjectMeta(labels={"runtime_id": runtime_id}),
                    spec=k8s_client.V1PodSpec(
                        containers=[
                            k8s_client.V1Container(name="runtime", image="test-image")
                        ]
                    ),
                ),
            ),
        )

        apps_api.create_namespaced_deployment(namespace=namespace, body=deployment)

        # Query pods by label selector (as done in OpenHands)
        pods = core_api.list_namespaced_pod(
            namespace=namespace, label_selector=f"runtime_id={runtime_id}"
        )

        assert len(pods.items) == 1
        pod = pods.items[0]

        # Verify pod status (as checked in OpenHands get_pods_summary)
        assert pod.status.phase == "Running"
        assert pod.status.container_statuses is not None
        assert len(pod.status.container_statuses) == 1

        container_status = pod.status.container_statuses[0]
        assert container_status.name == "runtime"
        assert container_status.ready is True
        assert container_status.restart_count == 0
        assert container_status.state.running is not None

        # Test log retrieval (as done in OpenHands)
        logs = core_api.read_namespaced_pod_log(
            name=pod.metadata.name, namespace=namespace, container="runtime"
        )
        assert "Mock logs" in logs


def test_cascading_deletion_pattern():
    """Test the cascading deletion pattern used in OpenHands."""
    with mock_kubernetes() as mock_k8s:
        runtime_id = "test-runtime-789"
        namespace = "default"

        core_api = k8s_client.CoreV1Api()
        apps_api = k8s_client.AppsV1Api()
        policy_api = k8s_client.PolicyV1Api()

        # Create deployment
        deployment = k8s_client.V1Deployment(
            metadata=k8s_client.V1ObjectMeta(
                name=f"runtime-{runtime_id}", labels={"runtime_id": runtime_id}
            ),
            spec=k8s_client.V1DeploymentSpec(
                replicas=1,
                selector=k8s_client.V1LabelSelector(
                    match_labels={"runtime_id": runtime_id}
                ),
                template=k8s_client.V1PodTemplateSpec(
                    metadata=k8s_client.V1ObjectMeta(labels={"runtime_id": runtime_id}),
                    spec=k8s_client.V1PodSpec(
                        containers=[
                            k8s_client.V1Container(name="runtime", image="test")
                        ]
                    ),
                ),
            ),
        )

        created_deployment = apps_api.create_namespaced_deployment(
            namespace=namespace, body=deployment
        )

        # Create dependent resources with owner references
        owner_ref = k8s_client.V1OwnerReference(
            api_version="apps/v1",
            kind="Deployment",
            name=created_deployment.metadata.name,
            uid=created_deployment.metadata.uid,
        )

        # Service
        service = k8s_client.V1Service(
            metadata=k8s_client.V1ObjectMeta(
                name=f"runtime-{runtime_id}", owner_references=[owner_ref]
            ),
            spec=k8s_client.V1ServiceSpec(
                selector={"runtime_id": runtime_id},
                ports=[k8s_client.V1ServicePort(port=80)],
            ),
        )
        core_api.create_namespaced_service(namespace=namespace, body=service)

        # PVC
        pvc = k8s_client.V1PersistentVolumeClaim(
            metadata=k8s_client.V1ObjectMeta(
                name=f"runtime-{runtime_id}", owner_references=[owner_ref]
            ),
            spec=k8s_client.V1PersistentVolumeClaimSpec(
                access_modes=["ReadWriteOnce"],
                resources=k8s_client.V1ResourceRequirements(
                    requests={"storage": "1Gi"}
                ),
            ),
        )
        core_api.create_namespaced_persistent_volume_claim(
            namespace=namespace, body=pvc
        )

        # PDB
        pdb = k8s_client.V1PodDisruptionBudget(
            metadata=k8s_client.V1ObjectMeta(
                name=f"runtime-{runtime_id}", owner_references=[owner_ref]
            ),
            spec=k8s_client.V1PodDisruptionBudgetSpec(
                min_available=1,
                selector=k8s_client.V1LabelSelector(
                    match_labels={"runtime_id": runtime_id}
                ),
            ),
        )
        policy_api.create_namespaced_pod_disruption_budget(
            namespace=namespace, body=pdb
        )

        # Verify all resources exist
        assert core_api.read_namespaced_service(f"runtime-{runtime_id}", namespace)
        assert core_api.read_namespaced_persistent_volume_claim(
            f"runtime-{runtime_id}", namespace
        )
        assert policy_api.read_namespaced_pod_disruption_budget(
            f"runtime-{runtime_id}", namespace
        )

        pods_before = core_api.list_namespaced_pod(
            namespace=namespace, label_selector=f"runtime_id={runtime_id}"
        )
        assert len(pods_before.items) == 1

        # Delete deployment (should cascade to all dependent resources)
        apps_api.delete_namespaced_deployment(
            name=f"runtime-{runtime_id}", namespace=namespace
        )

        # Verify all dependent resources are deleted
        with pytest.raises(ApiException) as exc:
            core_api.read_namespaced_service(f"runtime-{runtime_id}", namespace)
        assert exc.value.status == 404

        with pytest.raises(ApiException) as exc:
            core_api.read_namespaced_persistent_volume_claim(
                f"runtime-{runtime_id}", namespace
            )
        assert exc.value.status == 404

        with pytest.raises(ApiException) as exc:
            policy_api.read_namespaced_pod_disruption_budget(
                f"runtime-{runtime_id}", namespace
            )
        assert exc.value.status == 404

        # Verify pods are also deleted
        pods_after = core_api.list_namespaced_pod(
            namespace=namespace, label_selector=f"runtime_id={runtime_id}"
        )
        assert len(pods_after.items) == 0


def test_custom_objects_httproute():
    """Test custom objects API for HTTPRoute (Gateway API)."""
    with mock_kubernetes() as mock_k8s:
        runtime_id = "test-runtime-gateway"
        namespace = "default"

        custom_api = k8s_client.CustomObjectsApi()

        # Create HTTPRoute (as done in OpenHands for Gateway API mode)
        httproute_manifest = {
            "apiVersion": "gateway.networking.k8s.io/v1",
            "kind": "HTTPRoute",
            "metadata": {
                "name": f"runtime-{runtime_id}",
                "namespace": namespace,
                "labels": {"runtime_id": runtime_id},
            },
            "spec": {
                "parentRefs": [{"name": "gateway", "namespace": "gateway-system"}],
                "hostnames": [f"{runtime_id}.example.com"],
                "rules": [
                    {
                        "matches": [{"path": {"type": "PathPrefix", "value": "/"}}],
                        "backendRefs": [
                            {"name": f"runtime-{runtime_id}", "port": 8000}
                        ],
                    }
                ],
            },
        }

        created_httproute = custom_api.create_namespaced_custom_object(
            group="gateway.networking.k8s.io",
            version="v1",
            namespace=namespace,
            plural="httproutes",
            body=httproute_manifest,
        )

        assert created_httproute["metadata"]["name"] == f"runtime-{runtime_id}"

        # Retrieve the HTTPRoute
        retrieved_httproute = custom_api.get_namespaced_custom_object(
            group="gateway.networking.k8s.io",
            version="v1",
            namespace=namespace,
            plural="httproutes",
            name=f"runtime-{runtime_id}",
        )

        assert retrieved_httproute["metadata"]["name"] == f"runtime-{runtime_id}"


if __name__ == "__main__":
    pytest.main([__file__])
