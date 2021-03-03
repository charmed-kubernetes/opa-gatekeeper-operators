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


`$ juju add-model gatekeeper`


###  Deploy

```
$ juju deploy gatekeeper-audit --channel=beta
$ juju deploy gatekeeper-manager --channel=beta

```

### Post deployment steps

```
$ kubectl apply -f yaml/sync.yaml
$ kubectl apply -f yaml/template-constraint.yaml
$ CA_CERT=$(kubectl get secrets -n opa gatekeeper-webhook-server-cert -o jsonpath="{.data.ca\.crt}")

$ kubectl patch validatingWebhookConfigurations opa-gatekeeper-validating-webhook-configuration --type='json' -p='[{"op": "replace", "path": "/webhooks/0/clientConfig/caBundle", "value":'"${CA_CERT}"'}]'
$ kubectl patch validatingWebhookConfigurations opa-gatekeeper-validating-webhook-configuration --type='json' -p='[{"op": "replace", "path": "/webhooks/1/clientConfig/caBundle", "value":'"${CA_CERT}"'}]'


```