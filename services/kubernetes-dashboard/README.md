# About

This component needs `helmfile` and the `helm diff` and `helmfile-secrets` plugins to be installed:

```shell
brew install helmfile helm
helm plugin install https://github.com/databus23/helm-diff
helm plugin install https://github.com/jkroepke/helm-secrets
```

Remember: `.gotmpl` files will be rendered to create the final values file. It will be evaluated first.

## Deployement

To deploy the component, run the following command:

```bash
ENV=dev make deploy
```

To undeploy the component, run the following command:

```bash
ENV=dev make undeploy
```

## Provisioning

The component requires to apply changes on the following resources:

- aws/data/005_s3_buckets/
- aws/data/008_rds/

To provision the component, run the following command:

```bash
terraform init
terraform plan
terraform apply -auto-approve
```
