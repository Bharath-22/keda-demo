# keda-demo

# Prerequisites:
  An host where this set of script runs, this host should have the following:
  1. Preferably ubuntu OS or any other similar distros and to be run on bash or zsh shell terminals.
  2. Host should have access to internet and preferably run as sudoers.
  3. Python3 installed.
  4. Access to the intended kubernetes cluster, and it should already have a kubeconfig file generated.


# Steps to run the scripts and folders structure:

  1. Initial setup
  
  Extract the files from simplismart-assesment.zip file, within you will find a file named prerequisite.sh. Run this [bash prerequisite.sh] to install some prerequisite python packages and helm as well. Then there is one more file - setup.py. Run this python script in the host’s terminal [python3 setup.py].
  This will create a listener on port 8080 on the host, which serves the set of assessment apis. [Note: Please make sure there are no other application on the host using 8080 port at the time of running this script]. Now open a new terminal where you can run curls for initiating the apis

  2. Configuring kubectl to use the provided cluster -

  The listener is configured to serve some apis, for configuring and connecting to the kubernetes cluster. Utilise the /connect api, which connects to your kubernetes cluster which is mapped via the kube-config file that you provide. The api tries to connect to the kubernetes cluster and gives result. The curl for testing this api is given below:

  ```
   curl -X POST http://localhost:8080/connect \
  -H "Content-Type: application/json" \
  -d '{
    "clusterName": "example-cluster",
    "kubeconfigPath": "/path/to/your/kubeconfig"
  }'
  ```

  3. Install KEDA via helm and verify whether keda-operator is running -

  Use the /install-keda api which requires cluster-name in the request body as a parameter. The sample curl for this request is given below

  ```
  curl -X POST http://localhost:8080/install-keda \
  -H "Content-Type: application/json" \
  -d '{
    "clusterName": "example-cluster"
  }'
  ```

  4. Deployment of an application with a given parameters - 

  Use /deploy api which takes these input parameters:
    a. cluster name of the kubernetes cluster
    b. image which is a publicly available docker image 
    c. container port to export, Note: only one port is expected for this
    d. container cpu request in milicores, for ex: 100m
    e. container memory request in Ki/Mi/Gi, for ex: 10Mi
    f. container cpu limit in milicores, for ex: 100m
    g. container memory limit in Ki/Mi/Gi, for ex: 10Mi
    h. container cpu threshold for the keda scaledobject for the deployment, expecting a number between 1-100
    i. container memory threshold for the keda scaledobject for the deployment, expecting a number between 1-100
  Note: I am considering the cpu and memory as the trigger for the scaledobject of the deployment.
  The sample curl for this request is given below 

  ```
  curl -X POST http://localhost:8080/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "clusterName": "example-cluster",
    "replacements": {
      "image": "my-docker-image:v1.0",
      "containerport": "8080",
      "cpurequest": "200m",
      "memoryrequest": "128Mi",
      "cpulimit": "500m",
      "memorylimit": "256Mi"
      "cputhreshold": "50"
      "memorythreshold": "50"
    }
  }'
  ```
  
  This returns the deployment id and service endpoint and scaling configuration details.

5. Health status of the deployment -

Use the /status api which takes the cluster name and deployment id (which is provided from the /deploy api) as the parameters. then return the status of the deployment and cpu and memory usage of the pods associated with it
The sample curl for this request is given below

```
curl -X POST http://localhost:8080/status \
-H "Content-Type: application/json" \
-d '{
  "clusterName": "example-cluster",
  "deploymentId": "example-deployment"
}'
```