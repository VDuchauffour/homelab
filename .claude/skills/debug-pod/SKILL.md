______________________________________________________________________

## name: debug-pod description: Troubleshoot Kubernetes pod issues. Use when diagnosing CrashLoopBackOff, ImagePullBackOff, Pending pods, GPU problems, or any pod that is not running correctly. compatibility: Requires kubectl metadata: author: homelab version: "1.0"

# Debug Kubernetes Pod

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

## iGPU App Restart (Scale-Down/Scale-Up)

Apps using Intel iGPU resources (`gpu.intel.com/i915`) and hostPath `/dev/dri` may not cleanly release the GPU device on a simple `kubectl rollout restart`. Use the scale-down/scale-up procedure instead:

```shell
# 1. Scale deployment to 0
kubectl scale deployment <app-name> -n <namespace> --replicas=0

# 2. Wait for pod to fully terminate
kubectl wait --for=delete pod -l app.kubernetes.io/name=<app-name> -n <namespace> --timeout=120s

# 3. Scale back to 1
kubectl scale deployment <app-name> -n <namespace> --replicas=1

# 4. Verify pod is running
kubectl get pods -n <namespace> -l app.kubernetes.io/name=<app-name> -w
```

**When to use this**: GPU device stuck, transcoding errors, or after host-level changes to `/dev/dri`.

**Known iGPU apps**: jellyfin (`media-center`), tdarr (`media-center`).
