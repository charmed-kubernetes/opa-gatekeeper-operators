# Kubernetes Open Policy Agent Operator


## Description

This repo contains the charm for the Audit agent operator

## Usage

### bootstrap (if new to juju)


```
$ sudo snap install juju --classic

$ k8s_name=yournaminghere

$ juju add-k8s ${k8s_name}-cloud

$ juju bootstrap ${k8s_name}-cloud ${k8s_name}

```

To deploy run:

### Add Model

```
$ NAMESPACE=gatekeeper
$ juju add-model ${NAMESPACE}

```


###  Deploy

```
$ juju deploy gatekeeper-audit --channel=beta
$ juju deploy gatekeeper-manager --channel=beta

```


### Post deployment steps

```
$ kubectl apply -f docs/gatekeeper-rb.yaml
$ CA_CERT=$(kubectl get secrets -n gatekeeper gatekeeper-webhook-server-cert -o jsonpath="{.data.ca\.crt}")

$ CA_CERT=$(kubectl get secrets -n ${NAMESPACE} gatekeeper-webhook-server-cert -o jsonpath="{.data.ca\.crt}")
$ for i in {0..1}; do kubectl patch validatingWebhookConfigurations ${NAMESPACE}-gatekeeper-validating-webhook-configuration --type='json' -p='[{"op": "replace", "path": "/webhooks/'"$i"'/clientConfig/caBundle", "value":'"${CA_CERT}"'}]'; done
$ kubectl apply -f docs/gatekeeper-rb.yaml

```

## Developing
To get started ensure you have

- Microk8s (Or any other K8s)
- Juju
- Charmcraft `sudo snap install charmcraft`


## Testing

```
$ tox -e lint,unit,integration
```
## Development Environment Installation

### Prerequisites


1. [Install `microk8s`](https://microk8s.io/)
1. [Install `charmcraft`](https://github.com/canonical/charmcraft)
1. Create a cluster: `microk8s install --cpu=4 --mem=8`
1. Add the required addons: `microk8s enable storage dns`
1. Export the current kubeconfig: `microk8s config > kube.conf; export KUBECONFIG=kube.conf`

