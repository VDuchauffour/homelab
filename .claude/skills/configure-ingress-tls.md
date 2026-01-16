# Configure Ingress with TLS

Set up Traefik ingress with TLS certificates.

## Usage

```
/configure-ingress-tls <app-name> <hostname>
```

## Local Network (mkcert CA)

For internal `.home.arpa` domains using the local CA:

```yaml
ingress:
  enabled: true
  className: traefik
  annotations:
    kubernetes.io/ingress.class: traefik
    cert-manager.io/cluster-issuer: mkcert-ca
  hosts:
    - host: <app-name>.home.arpa
      paths:
        - path: /
          pathType: Prefix
  tls:
    - hosts:
        - <app-name>.home.arpa
      secretName: <app-name>-mkcert-tls
```

## Public Access (Let's Encrypt via FRP)

For publicly accessible apps through the Scaleway proxy:

1. App uses regular ingress (no TLS annotation needed - Caddy handles it)
2. Configure FRP client in homelab to tunnel the service
3. Add route in Scaleway proxy's Caddyfile

## Recreate Local CA

If the mkcert CA needs to be recreated:

```shell
CERT_DIR=$(mkcert -CAROOT)
kubectl create secret tls mkcert-ca-key-pair \
  -n cert-manager \
  --cert=$CERT_DIR/rootCA.pem \
  --key=$CERT_DIR/rootCA-key.pem

kubectl apply -f kubernetes/infra/cert-manager/manifests/mkcert-ca-issuer.yaml
```

## Verify Certificate

```shell
# Check certificate resource
kubectl get certificate -n <namespace>

# Check secret
kubectl get secret -n <namespace> <app-name>-mkcert-tls

# Describe for issues
kubectl describe certificate -n <namespace> <app-name>-tls
```

## ClusterIssuers

Available issuers:

- `mkcert-ca`: Local network certificates (defined in `kubernetes/infra/cert-manager/manifests/mkcert-ca-issuer.yaml`)
- `letsencrypt-prod`: Public Let's Encrypt (defined in `kubernetes/infra/cert-manager/manifests/letsencrypt-ca-issuer.yaml`)
