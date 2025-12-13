#!/usr/bin/env python3
"""
Basic usage examples for Mockernetes.

This file demonstrates how to use Mockernetes to mock Kubernetes APIs
in your tests, using patterns similar to the OpenHands runtime-api.
"""

from kubernetes import client as k8s_client
from mockernetes import mock_kubernetes


def example_basic_pod_operations():
    """Example: Basic pod operations with mocked Kubernetes API."""
    print("=== Basic Pod Operations ===")
    
    with mock_kubernetes() as mock_k8s:
        # Get the API client - this is now mocked
        core_api = k8s_client.CoreV1Api()
        
        # Create a pod
        pod = k8s_client.V1Pod(
            metadata=k8s_client.V1ObjectMeta(
                name="example-pod",
                labels={"app": "example"}
            ),
            spec=k8s_client.V1PodSpec(
                containers=[
                    k8s_client.V1Container(
                        name="web",
                        image="nginx:latest",
                        ports=[k8s_client.V1ContainerPort(container_port=80)]
                    )
                ]
            )
        )
        
        # Create the pod
        created_pod = core_api.create_namespaced_pod(namespace="default", body=pod)
        print(f"Created pod: {created_pod.metadata.name}")
        print(f"Pod status: {created_pod.status.phase}")
        print(f"Pod UID: {created_pod.metadata.uid}")
        
        # List pods
        pods = core_api.list_namespaced_pod(namespace="default")
        print(f"Total pods: {len(pods.items)}")
        
        # List pods with label selector
        app_pods = core_api.list_namespaced_pod(
            namespace="default", 
            label_selector="app=example"
        )
        print(f"Pods with app=example: {len(app_pods.items)}")
        
        # Get pod logs
        logs = core_api.read_namespaced_pod_log(
            name="example-pod",
            namespace="default",
            container="web"
        )
        print(f"Pod logs: {logs}")


def example_deployment_with_controller_simulation():
    """Example: Deployment creation with automatic pod generation."""
    print("\n=== Deployment with Controller Simulation ===")
    
    with mock_kubernetes() as mock_k8s:
        apps_api = k8s_client.AppsV1Api()
        core_api = k8s_client.CoreV1Api()
        
        # Create a deployment
        deployment = k8s_client.V1Deployment(
            metadata=k8s_client.V1ObjectMeta(
                name="web-deployment",
                labels={"app": "web"}
            ),
            spec=k8s_client.V1DeploymentSpec(
                replicas=3,
                selector=k8s_client.V1LabelSelector(
                    match_labels={"app": "web"}
                ),
                template=k8s_client.V1PodTemplateSpec(
                    metadata=k8s_client.V1ObjectMeta(
                        labels={"app": "web"}
                    ),
                    spec=k8s_client.V1PodSpec(
                        containers=[
                            k8s_client.V1Container(
                                name="web",
                                image="nginx:latest"
                            )
                        ]
                    )
                )
            )
        )
        
        # Create the deployment
        created_deployment = apps_api.create_namespaced_deployment(
            namespace="default",
            body=deployment
        )
        print(f"Created deployment: {created_deployment.metadata.name}")
        print(f"Desired replicas: {created_deployment.spec.replicas}")
        print(f"Ready replicas: {created_deployment.status.ready_replicas}")
        
        # Check that pods were automatically created
        pods = core_api.list_namespaced_pod(
            namespace="default",
            label_selector="app=web"
        )
        print(f"Pods created by deployment: {len(pods.items)}")
        
        # Verify owner references
        for pod in pods.items:
            if pod.metadata.owner_references:
                owner = pod.metadata.owner_references[0]
                print(f"Pod {pod.metadata.name} owned by {owner.kind}/{owner.name}")


if __name__ == "__main__":
    print("Mockernetes Usage Examples")
    print("=" * 50)
    
    example_basic_pod_operations()
    example_deployment_with_controller_simulation()
    
    print("\n" + "=" * 50)
    print("Examples completed successfully!")
    print("Mockernetes is working as a drop-in replacement for Kubernetes APIs.")