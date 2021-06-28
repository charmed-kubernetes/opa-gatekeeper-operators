# Gatekeeper operator for Kubernetes

## Getting started (Quickstart)

### Bootstrap (If new to Juju)


```
$ sudo snap install juju --classic

$ K8S_NAME=YourNamingHere

$ juju add-k8s ${K8S_NAME}-cloud

$ juju bootstrap ${K8S_NAME}-cloud ${K8S_NAME}

```


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
$ NAMESPACE=your-namespace
$ CA_CERT=$(kubectl get secrets -n gatekeeper gatekeeper-webhook-server-cert -o jsonpath="{.data.ca\.crt}")

$ for i in {0..1}; do kubectl patch validatingWebhookConfigurations ${NAMESPACE}-gatekeeper-validating-webhook-configuration --type='json' -p='[{"op": "replace", "path": "/webhooks/'"$i"'/clientConfig/caBundle", "value":'"${CA_CERT}"'}]'; done

```

### Applying policies

```
$ kubectl apply -f docs/policy-example.yaml
$ kubectl apply -f docs/policy-spec-example.yaml

```
