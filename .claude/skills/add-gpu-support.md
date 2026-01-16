# Add Intel GPU Support

Configure a pod to use Intel iGPU for hardware acceleration (QSV/VAAPI).

## Usage

```
/add-gpu-support <app-name>
```

## Prerequisites

- Intel Device Plugins Operator installed
- GPU Device Plugin deployed
- Node has Intel iGPU

Check status:

```shell
kubectl get gpudeviceplugins
```

## Values Configuration

Add to your `values.yaml`:

```yaml
# Pod security context for GPU access
podSecurityContext:
  supplementalGroups:
    - 993  # render group
  fsGroup: 993

# Container security context
securityContext:
  runAsUser: 1000
  runAsGroup: 1000
  supplementalGroups:
    - 993
  capabilities:
    add:
      - SYS_ADMIN
    drop:
      - ALL
  privileged: false

# Mount GPU device
extraVolumes:
  - name: hwa
    hostPath:
      path: /dev/dri

extraVolumeMounts:
  - name: hwa
    mountPath: /dev/dri

# Request GPU resource
resources:
  limits:
    gpu.intel.com/i915: '1'
  requests:
    gpu.intel.com/i915: '1'
```

## Verification

### On Host

```shell
# Check GPU usage
intel_gpu_top

# Check VAAPI profiles
vainfo

# Check OpenCL
clinfo
```

### In Pod

```shell
kubectl exec -it -n <namespace> <pod> -- ls -la /dev/dri
```

## Reference Apps

- `kubernetes/apps/jellyfin/values.yaml` - Full GPU config example
- `kubernetes/apps/tdarr/values.yaml` - Transcoding with GPU

## Troubleshooting

- **No GPU available**: Check `kubectl get nodes -o yaml | grep -A5 allocatable`
- **Permission denied**: Verify supplementalGroups includes render group (usually 993)
- **Device not found**: Ensure `/dev/dri` exists on host node
