# Deploy Helmfile Application

Deploy or update a Kubernetes application using Helmfile.

## Usage

```
/deploy-helmfile-app <app-name>
```

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

3. Apply any pre-requisite manifests:

   ```shell
   kubectl apply -f manifests/
   ```

4. Run helmfile diff to preview changes:

   ```shell
   helmfile diff
   ```

5. Apply the release:

   ```shell
   helmfile apply
   ```

6. Verify deployment:

   ```shell
   kubectl get pods -n <namespace>
   kubectl get ingress -n <namespace>
   ```

## Troubleshooting

- Check pod logs: `kubectl logs -n <namespace> <pod-name>`
- Describe pod for events: `kubectl describe pod -n <namespace> <pod-name>`
- Check PVC status: `kubectl get pvc -n <namespace>`
