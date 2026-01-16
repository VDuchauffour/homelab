# Debug Kubernetes Pod

Troubleshoot pod issues in the cluster.

## Usage

```
/debug-pod <namespace> <pod-name-or-selector>
```

## Diagnostic Steps

### 1. Check Pod Status

```shell
# List pods in namespace
kubectl get pods -n <namespace>

# Get pod details
kubectl describe pod -n <namespace> <pod-name>
```

### 2. Check Logs

```shell
# Current logs
kubectl logs -n <namespace> <pod-name>

# Previous container logs (if restarting)
kubectl logs -n <namespace> <pod-name> --previous

# Follow logs
kubectl logs -n <namespace> <pod-name> -f

# Multi-container pod
kubectl logs -n <namespace> <pod-name> -c <container-name>
```

### 3. Check Events

```shell
kubectl get events -n <namespace> --sort-by='.lastTimestamp'
```

### 4. Check Resources

```shell
# PVC status
kubectl get pvc -n <namespace>

# Services
kubectl get svc -n <namespace>

# Ingress
kubectl get ingress -n <namespace>

# ConfigMaps/Secrets
kubectl get configmap,secret -n <namespace>
```

### 5. Interactive Debug

```shell
# Exec into running container
kubectl exec -it -n <namespace> <pod-name> -- /bin/sh

# Debug with ephemeral container
kubectl debug -it -n <namespace> <pod-name> --image=busybox
```

### 6. Resource Usage

```shell
kubectl top pod -n <namespace>
kubectl top node
```

## Common Issues

### ImagePullBackOff

- Check image name and tag
- Verify registry credentials if private

### CrashLoopBackOff

- Check logs for application errors
- Verify environment variables
- Check resource limits

### Pending

- Check node resources: `kubectl describe nodes`
- Check PVC binding: `kubectl get pvc -n <namespace>`
- Check node selectors/affinity

### GPU Issues (Intel iGPU)

```shell
# Check GPU plugin status
kubectl get gpudeviceplugins

# On host
intel_gpu_top
```
