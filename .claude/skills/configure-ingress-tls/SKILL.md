______________________________________________________________________

## name: configure-ingress-tls description: Set up Traefik ingress with TLS certificates. Use when configuring local mkcert-CA TLS, public Let's Encrypt TLS via Pangolin, or troubleshooting certificate issues. compatibility: Requires kubectl, mkcert, and cert-manager in-cluster metadata: author: homelab version: "1.0"

# Configure Ingress with TLS

## Local Network (mkcert CA)

For internal `.<local-domain-name>` domains using the local CA:

```yaml
ingress:
  enabled: true
  className: traefik
  annotations:
    kubernetes.io/ingress.class: traefik
    cert-manager.io/cluster-issuer: mkcert-ca
  hosts:
    - host: <app-name>.<local-domain-name>
      paths:
        - path: /
          pathType: Prefix
  tls:
    - hosts:
        - <app-name>.<local-domain-name>
      secretName: <app-name>-mkcert-tls
```

## Public Access (via Pangolin Blueprint)

For publicly accessible apps through the Scaleway proxy:

1. App uses regular ingress with local TLS (same as above)
2. Add a resource block to the Pangolin blueprint: `kubernetes/infra/pangolin-newt/manifests/blueprint.yaml` (maintain alphabetical order by resource key)
3. Set `full-domain`, target `hostname`/`port`, auth settings (`sso-enabled`, `whitelist-users`), and healthcheck
4. Deploy: `vals eval -f manifests/blueprint.yaml | kubectl apply -f - && kubectl rollout restart deployment/fossorial-newt-main-tunnel -n fossorial`

**Note:** TLS for public access is handled by Traefik (Let's Encrypt) on the Scaleway proxy — no cert-manager annotation needed for the public domain. The Newt tunnel forwards traffic to the K8s service ClusterIP directly.

## Recreate Local CA

If the mkcert CA needs to be recreated:

```shell
CERT_DIR=$(mkcert -CAROOT)
kubectl create secret tls mkcert-ca-key-pair \
  -n cert-manager \
  --cert=$CERT_DIR/rootCA.pem \
  --key=$CERT_DIR/rootCA-key.pem

kubectl apply -f kubernetes/cluster/certificates/mkcert-ca-issuer.yaml
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

- `mkcert-ca`: Local network certificates (defined in `kubernetes/cluster/certificates/mkcert-ca-issuer.yaml`)
- `letsencrypt-prod`: Public Let's Encrypt (defined in `kubernetes/cluster/certificates/letsencrypt-ca-issuer.yaml`)
