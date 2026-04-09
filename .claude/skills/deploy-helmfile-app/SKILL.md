______________________________________________________________________

## name: deploy-helmfile-app description: Deploy or update a Kubernetes application using Helmfile. Use when deploying, redeploying, or updating any app or infra component managed by Helmfile. compatibility: Requires helmfile, helm, kubectl, and vals CLI tools metadata: author: homelab version: "1.0"

# Deploy Helmfile Application

## Steps

1. Navigate to the app directory:

   ```shell
   cd kubernetes/apps/<app-name>
   # OR for infra components:
   cd kubernetes/infra/<app-name>
   ```

2. Check for required manifests (PVs, secrets, namespaces):

   ```shell
   ls manifests/
   ```

3. Apply any pre-requisite manifests (using vals for secret substitution):

   ```shell
   vals eval -f manifests/<file>.yaml | kubectl apply -f -
   ```

4. Run helmfile diff to preview changes:

   ```shell
   helmfile diff
   ```

5. Apply the release:

   ```shell
   helmfile apply
   ```

6. **Glance only** — Helm doesn't detect ConfigMap content changes, so force a restart:

   ```shell
   make glance-update
   ```

7. Verify deployment:

   ```shell
   kubectl get pods -n <namespace>
   kubectl get ingress -n <namespace>
   ```

## Troubleshooting

- Check pod logs: `kubectl logs -n <namespace> <pod-name>`
- Describe pod for events: `kubectl describe pod -n <namespace> <pod-name>`
- Check PVC status: `kubectl get pvc -n <namespace>`
