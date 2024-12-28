from flask import Flask, jsonify, request
from kubernetes import client, config, utils
import subprocess
import time
import yaml

app = Flask(__name__)

# Global dictionary to persist Kubernetes clients
k8s_clients = {}

def get_k8s_client(kubeconfig_path):
    """Initialize a Kubernetes client."""
    config.load_kube_config(config_file=kubeconfig_path)
    return client.CoreV1Api()

@app.route('/connect', methods=['POST'])
def connect_cluster():
    """Connect to a Kubernetes cluster and initialize the client."""
    data = request.get_json()

    # Validate input
    if not data or 'clusterName' not in data or 'kubeconfigPath' not in data:
        return jsonify({"error": "Request must contain 'clusterName' and 'kubeconfigPath' in the body."}), 400

    cluster_name = data['clusterName']
    kubeconfig_path = data['kubeconfigPath']

    try:
        # Initialize the Kubernetes client and store it in the global dictionary
        k8s_clients[cluster_name] = get_k8s_client(kubeconfig_path)
        return jsonify({"message": f"Connected to cluster {cluster_name} successfully."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/install-keda', methods=['POST'])
def install_keda():
    """Install KEDA using Helm."""
    data = request.get_json()

    # Validate input
    if not data or 'clusterName' not in data:
        return jsonify({"error": "Request must contain 'clusterName' in the body."}), 400

    cluster_name = data['clusterName']

    # Check if the client exists for the cluster
    if cluster_name not in k8s_clients:
        return jsonify({"error": f"No connection found for cluster {cluster_name}. Please call /connect first."}), 400

    try:
        # Run the Helm install command
        subprocess.run(
            ["helm", "repo", "add", "kedacore", "https://kedacore.github.io/charts"],
            check=True, text=True, capture_output=True
        )
        subprocess.run(
            ["helm", "repo", "update"],
            check=True, text=True, capture_output=True
        )
        subprocess.run(
            ["helm", "install", "keda", "kedacore/keda", "--namespace", "keda", "--create-namespace"],
            check=True, text=True, capture_output=True
        )

        # Wait for 30 seconds to allow KEDA to deploy
        time.sleep(30)

        # Verify if the keda-operator pod is running
        v1 = k8s_clients[cluster_name]
        pods = v1.list_namespaced_pod(namespace="keda")
        for pod in pods.items:
            if "keda-operator" in pod.metadata.name and pod.status.phase == "Running":
                return jsonify({"message": "KEDA successfully installed and keda-operator pod is running."})

        return jsonify({"error": "KEDA installed, but keda-operator pod is not running."}), 500

    except subprocess.CalledProcessError as e:
        return jsonify({"error": e.stderr}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/deploy', methods=['POST'])
def deploy_with_replacements():
    """Replace placeholders in a static YAML file and deploy it to the Kubernetes cluster."""
    data = request.get_json()

    # Validate input
    if not data or 'clusterName' not in data or 'replacements' not in data:
        return jsonify({"error": "Request must contain 'clusterName' and 'replacements' in the body."}), 400

    cluster_name = data['clusterName']
    file_path = "deployment/deployment.yaml"
    replacements = data['replacements']

    # Check if the client exists for the cluster
    if cluster_name not in k8s_clients:
        return jsonify({"error": f"No connection found for cluster {cluster_name}. Please call /connect first."}), 400

    try:
        # Read the file and replace placeholders
        with open(file_path, 'r') as f:
            yaml_content = f.read()

        for placeholder, value in replacements.items():
            yaml_content = yaml_content.replace(f"__{placeholder}__", value)

        # Parse the modified YAML
        yaml_objects = list(yaml.safe_load_all(yaml_content))

        # Deploy the YAML objects to the cluster
        v1 = k8s_clients[cluster_name]
        for obj in yaml_objects:
            utils.create_from_dict(v1.api_client, obj)

        return jsonify({"message": "Deployment successful.","Deployment-Id": "example-app","Endpoint inside Cluster": f"example-app.default.svc.cluster.local:{replacements['containerport']}","Scaling Configuration": f"Minimum 1 pod which can scale up to 10 pods based on the threshold of {replacements['cputhreshold']}"})

    except FileNotFoundError:
        return jsonify({"error": f"File '{file_path}' not found."}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/status', methods=['POST'])
def get_deployment_status():
    """Get the status of a deployment and its pods, including CPU and memory metrics."""
    data = request.get_json()

    # Validate input
    if not data or 'clusterName' not in data or 'deploymentId' not in data:
        return jsonify({"error": "Request must contain 'clusterName' and 'deploymentId' in the body."}), 400

    cluster_name = data['clusterName']
    deployment_id = data['deploymentId']

    # Check if the client exists for the cluster
    if cluster_name not in k8s_clients:
        return jsonify({"error": f"No connection found for cluster {cluster_name}. Please call /connect first."}), 400

    try:
        # Retrieve the Kubernetes client
        v1 = k8s_clients[cluster_name]
        apps_v1 = client.AppsV1Api(client.ApiClient())

        # Get deployment status
        deployment = apps_v1.read_namespaced_deployment_status(deployment_id, namespace="default")
        deployment_status = {
            "replicas": deployment.status.replicas,
            "availableReplicas": deployment.status.available_replicas,
            "unavailableReplicas": deployment.status.unavailable_replicas
        }

        # Get pod metrics
        pods = v1.list_namespaced_pod(namespace="default", label_selector=f"app={deployment_id}")
        pod_metrics = []
        for pod in pods.items:
            pod_data = {
                "name": pod.metadata.name,
                "phase": pod.status.phase,
                "cpu": None,
                "memory": None
            }

            # Fetch resource usage using metrics API (requires metrics-server to be installed)
            try:
                metrics = v1.read_namespaced_pod_metrics(pod.metadata.name, namespace="default")
                for container in metrics.containers:
                    pod_data["cpu"] = container.usage.get("cpu")
                    pod_data["memory"] = container.usage.get("memory")
            except Exception:
                pod_data["cpu"] = "Metrics not available"
                pod_data["memory"] = "Metrics not available"

            pod_metrics.append(pod_data)

        return jsonify({
            "deploymentStatus": deployment_status,
            "podMetrics": pod_metrics
        })

    except client.exceptions.ApiException as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
