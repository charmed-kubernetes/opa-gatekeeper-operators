# Open Policy Agent Gatekeeper Webhook Operator
## Description

This is the OPA Gatekeeper webhook operator charm.
[OPA gatekeeper](https://open-policy-agent.github.io/gatekeeper/website/docs/)
is an open source, general-purpose policy engine that enables unified,
context-aware policy enforcement.

The `opa-manager-operator` charm is used to apply policies to incomming
kubernetes API requests.

## Usage
### Metrics
Gatekeeper Controller Manager metrics can be integrated with a deployed
[prometheus-k8s operator](https://charmhub.io/prometheus-k8s) using the following command:
```commandline
$ juju relate gatekeeper-controller-manager prometheus-k8s
```

If you would like to rely on the [grafana-agent-k8s operator](https://charmhub.io/grafana-agent-k8s) to push metrics,
you can use the commands below:
```commandline
$ juju relate grafana-agent-k8s gatekeeper-controller-manager
$ juju relate grafana-agent-k8s:send-remote-write prometheus-k8s:receive-remote-write
```

### Applying policies
There is an [example policy](docs) in this repo. To try it run:
```commandline
kubectl apply -f policy-example.yaml
kubectl apply -f policy-spec-example.yaml
```

After applying this policy all namespaces will need to have the label `gatekeeper`.
Existing namespaces are not affected by this.

### Getting policies
To list all the policies that are currently applied run:
```
juju run-action {unit_name} list-constraints --wait
```

## Developing
The easiest way to test gatekeeper locally is with [MicroK8s](https://microk8s.io/).
Once you have installed microk8s and bootstrapped a Juju controller you are ready to
build and deploy the charm:

```commandline
charmcraft build
juju add-model gatekeeper
juju deploy --trust charm --resource gatekeeper-image=openpolicyagent/gatekeeper:v3.9.0
```

## Testing

```commandline
$ tox
```
