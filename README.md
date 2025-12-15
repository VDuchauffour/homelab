# homelab

## Recreate CA for local network

```shell
CERT_DIR=$(mkcert -CAROOT)
kubectl create secret tls mkcert-ca-key-pair -n cert-manager --cert=$CERT_DIR/rootCA.pem --key=$CERT_DIR/rootCA-key.pem
kubectl apply -f cluster/cert-manager/manifests/mkcert-ca-issuer.yaml
```

In the ingress, adding the following annotation with cert-manager will:

- Create a Certificate resource
- Issue a leaf cert signed by your mkcert CA
- Manage renewals automatically
- Maintain the qbittorrent-mkcert-tls Secret

```yaml
ingress:
  enabled: true
  className: traefik
  annotations:
    kubernetes.io/ingress.class: traefik
    cert-manager.io/cluster-issuer: mkcert-ca
```

## Password generation recommandation

```shell
pwgen -scyn 32 1
or
openssl rand -base64 32
```

## Misc

To check the usage of iGPU (through Intel QSV or VAAPI) use the command `intel_gpu_top` from the package `intel-gpu-tools`.

## Acknowledgments

- Some charts are inspired by [rtomik's helm-charts repo](https://github.com/rtomik/helm-charts)
