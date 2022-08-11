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

## Developing
To get started ensure you have

- Microk8s (Or any other K8s)
- Juju
- Charmcraft `sudo snap install charmcraft`


## Testing

```
$ tox -e lint,unit,integration
```
