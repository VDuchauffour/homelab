# how to

Run once to install the operator, then another time when the operator deployement is available:

```shell
helmfile -l name=cnpg-database sync --include-transitive-needs

# or

helmfile -l name=cnpg-database sync --include-transitive-needs - services/cloudnative-pg/helmfile.yaml
```
