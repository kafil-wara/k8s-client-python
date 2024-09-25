import os
import logging
from kubernetes import client, config
from flask import Flask, jsonify, request
from kubernetes.client.rest import ApiException

app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.INFO)

# Load the Kubernetes config from the cluster
# config.load_incluster_config()

# Read the token directly from the service account token file
with open("/var/run/secrets/kubernetes.io/serviceaccount/token", "r") as token_file:
    token = token_file.read().strip()

# Read the Kubernetes API server URL from the environment variable
api_server = os.getenv("K8S_API_SERVER_URL")

# Log token and API server URL for debugging (Remove in production)
logging.info(f"Token from file: {token}")
logging.info(f"API Server URL: {api_server}")

@app.route('/cluster-details', methods=['GET'])
def get_cluster_details():
    # Set up the Kubernetes client configuration
    configuration = client.Configuration()
    configuration.host = api_server
    configuration.verify_ssl = False  # Use verify_ssl=True with CA cert in production

    # Use the token for authentication
    configuration.api_key = {"authorization": f"Bearer {token}"}
    client.Configuration.set_default(configuration)

    # Access the Kubernetes API
    core_v1 = client.CoreV1Api()

    try:
        # List all pods in all namespaces
        pods = core_v1.list_pod_for_all_namespaces()

        return jsonify({
            'pods': [pod.to_dict() for pod in pods.items],
        }), 200
    except ApiException as e:
        logging.error(f"Exception when calling the API: {e}")
        return jsonify(error=f"Exception when calling the API: {e}"), e.status

@app.route('/run-job', methods=['POST'])
def run_job():
    batch_v1 = client.BatchV1Api()
    # Define the Job name and namespace
    job_name = request.json.get('job_name', 'pi')
    namespace = request.json.get('namespace', 'default')

    # Define the Job configuration based on the example YAML
    job = client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=client.V1ObjectMeta(name=job_name),
        spec=client.V1JobSpec(
            template=client.V1PodTemplateSpec(
                spec=client.V1PodSpec(
                    restart_policy='Never',
                    containers=[
                        client.V1Container(
                            name="pi",
                            image="perl:5.34.0",
                            command=["perl", "-Mbignum=bpi", "-wle", "print bpi(2000)"]
                        )
                    ]
                )
            ),
            backoff_limit=4
        )
    )

    try:
        # Create the Job
        response = batch_v1.create_namespaced_job(
            body=job,
            namespace=namespace
        )
        return jsonify(
            message=f"Job {job_name} created successfully.",
            job=response.to_dict()
        ), 201
    except ApiException as e:
        return jsonify(
            error=f"Exception when creating the Job: {e}"
        ), e.status

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

