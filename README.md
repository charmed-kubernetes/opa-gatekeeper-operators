# Gatekeeper Operator for Kubernetes

## Overview
Gatekeeper is a validating webhook that enforces CRD-based policies
using the Open Policy Agent. Upstream documentation for Gatekeeper
can be found at https://open-policy-agent.github.io/gatekeeper/website/docs/
and for OPA at https://www.openpolicyagent.org/docs/latest/

There are 2 charms in this repo, the manager charm, which is responsible
for deploying the gatekeeper webhook and the audit charm, which is responsible
for deploying the gatekeeper auditing service. The webhook is responsible for
enforcing policies on incomming resource requests and audit is
responsible for checking for policy violations on existing resources.

## Building the charms
The charms can be built locally using [charmcraft](https://github.com/canonical/charmcraft):

```bash
charmcraft pack -p opa-audit-operator
charmcraft pack -p opa-manager-operator
```

## Deploying the charms
To deploy the charms run:

```bash
juju deploy --trust opa-manager-operator.charm --resource gatekeeper-image=openpolicyagent/gatekeeper:v3.9.0
juju deploy --trust opa-audit-operator.charm --resource gatekeeper-image=openpolicyagent/gatekeeper:v3.9.0
```

## Testing locally
The easiest way to test Gatekeeper locally is with MicroK8s.
Note that MicroK8s and Juju are not strictly build dependencies,
so you may need to install them yourself:

```bash
snap install juju --classic
snap install microk8s --classic
sudo usermod -aG microk8s $USER
sudo chown -f -R $USER ~/.kube
microk8s enable dns storage rbac
```

Once that is done, you can bootstrap a Juju controller into MicroK8s, add a
Kubernetes model, and deploy the charms:

```bash
juju bootstrap microk8s
juju add-model gatekeeper-system
juju deploy --trust ./opa-manager-operator.charm --resource gatekeeper-image=openpolicyagent/gatekeeper:v3.9.0
juju deploy --trust ./opa-audit-operator.charm --resource gatekeeper-image=openpolicyagent/gatekeeper:v3.9.0
```

Once both charms are deployed you can test applying the simple policy located at [docs](docs) by running:
```bash
microk8s kubectl apply -f docs/policy-example.yaml
microk8s kubectl apply -f docs/policy-spec-example.yaml
```

Applying these policies will force all new namespaces to include the label `gatekeeper`, you can test by running:
```bash
microk8s kubectl create ns test
```

This should return an error like this:
```console
Error from server (Forbidden): admission webhook "validation.gatekeeper.sh" denied the request: [ns-must-have-gk] you must provide labels: {"gatekeeper"}
```
