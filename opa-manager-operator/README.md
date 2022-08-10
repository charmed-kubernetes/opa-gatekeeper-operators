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
$ juju deploy --trust gatekeeper-controller-manager

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
