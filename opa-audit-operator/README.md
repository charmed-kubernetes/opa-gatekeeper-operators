# Open Policy Agent Gatekeeper Audit Operator
## Description

This is the OPA Gatekeeper audit operator charm.
[OPA gatekeeper](https://open-policy-agent.github.io/gatekeeper/website/docs/)
is an open source, general-purpose policy engine that enables unified,
context-aware policy enforcement.

The `opa-audit` charm is used to audit existing kubernetes API resources.

## Usage
### Metrics
Gatekeeper Audit metrics can be integrated with a deployed
[prometheus-k8s operator](https://charmhub.io/prometheus-k8s) using the following command:
```commandline
$ juju relate gatekeeper-audit prometheus-k8s
```

If you would like to rely on the [grafana-agent-k8s operator](https://charmhub.io/grafana-agent-k8s) to push metrics,
you can use the commands below:
```commandline
$ juju relate grafana-agent-k8s gatekeeper-audit
$ juju relate grafana-agent-k8s:send-remote-write prometheus-k8s:receive-remote-write
```

### Applying policies
There is an [example policy](docs) in this repo. To try it run:
```commandline
kubectl apply -f policy-example.yaml
kubectl apply -f policy-spec-example.yaml
```
After applying this policy all namespaces will be required to have the label `gatekeeper`.

### Reading Audit Results
As described on the official [docs](https://open-policy-agent.github.io/gatekeeper/website/docs/audit)
there are multiple ways to gather the audit results. The opa-audit-operator provides actions
to make it easier.
Any namespaces violating a constraint can be listed using the `get-violation` action, e.g. for the constraint described above:
```
juju run-action gatekeeper-audit/0 get-violation constraint-template=K8sRequiredLabels constraint=ns-must-have-gk --wait
```

To see how many resources violate each policy you need to run:
```
juju run-action gatekeeper-audit/0 list-violations --wait
```

### List policies
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
