# Kubernetes Open Policy Agent Operator


## Description


## Usage

TODO
 


## Developing

TODO 

## Testing

TODO
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

TODO

### Run a Test

TODO

### Destroy an application, for redeployment

TODO 

### Delete a Model

TODO



