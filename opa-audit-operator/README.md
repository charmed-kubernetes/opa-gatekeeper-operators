# spark-operator

This is a prototype [charm](https://charmhub.io/about#what-is-a-charm) for [the spark operator](https://github.com/GoogleCloudPlatform/spark-on-k8s-operator).

## Description

Deploying this charm will result in an installation of the [the spark operator](https://github.com/GoogleCloudPlatform/spark-on-k8s-operator) container. Where possible, the same configuration options are used.

## Usage

Install the charm buy building a deploying.

```sh
python -m charmcraft build
juju add-model spark
juju deploy ./spark-operator.charm
```

Deploy a spark application in the usual way. For example:

```sh
kubectl -n spark apply -f examples/spark-pi.yaml
```

### Changing Namespaces

The default configuration looks in the spark namespace for SparkApplications. Change this setting if you want to use another namespace.

The spark application also needs a service account to run. Create this yourself, or reuse the spark-operator service account if you want full privilidges.

## Developing

Create and activate a virtualenv with the development requirements:

    virtualenv -p python3 venv
    source venv/bin/activate
    pip install -r requirements-dev.txt

## Testing

The Python operator framework includes a very nice harness for testing
operator behaviour without full deployment. Just `run_tests`:

    ./run_tests

## Development Environment Installation

### Prerequisites

Note that the spark jobs typically set limits and need a CPU and a gig of ram. So we need to increase the default VM size.

1. [Install `microk8s`](https://microk8s.io/)
1. [Install `charmcraft`](https://github.com/canonical/charmcraft)
1. Create a cluster: `microk8s install --cpu=4 --mem=8`
1. Add the required addons: `microk8s enable storage dns`
1. Export the current kubeconfig: `microk8s config > kube.conf; export KUBECONFIG=kube.conf`

Wait for all the pods to be running before continuing.

Next, you need to install the juju OLM. But if you're using microk8s on OSX then it will use a VM. Juju tries to connect to the internal k8s address, so that doesn't work. Instead, there are some hidden settings where you can specify an external IP address (the IP address of the node). When you do that, juju will see this and use the correct IP/port.

1. `microk8s config | juju add-k8s mycluster --client`
1. `juju bootstrap mycluster --config controller-service-type=loadbalancer --config controller-external-ips="[$(multipass info microk8s-vm | grep IPv4 | awk '{print $2}')]"`

Note that you may need to unregister a controller if you've killed your VM. You can do this with: `juju unregister -y mycluster-localhost`

### Edit the Model Configuration
You can set the configuration of the Spark model by editing the file `config.yaml`.

1. `vim config.yaml`

### Build the Model

Again, this slightly depends on how you have your system setup, as `charmcraft` may or may not be in your path. I found that this command worked reliably in all situations.

1. `python -m charmcraft build`

### Add a Model, Copy the File Across, and Deploy

On OSX, you'll need to copy the charm across to the VM.

1. `juju add-model spark`
1. `juju deploy ./spark-operator.charm`

### Run a Test

1. `kubectl -n spark apply -f examples/spark-pi.yaml`

Note that this requires 1GB of ram to run (java!) so you will need to make sure your VM has enough RAM. By default microk8s uses 4G which is not enough.

### Destroy an application, for redeployment

1. `juju remove-application spark-operator --force --no-wait`

### Delete a Model

1. `microk8s juju destroy-model spark`

## Potential Roadmap

- Tests
- Tidy up pod spec code and args
- Have option to disable global role
- Mutating websocket
- Release to charm hub

## Future

- Consider re-implementing spark operator functionality? Take over responsibility of drivers and executors?
