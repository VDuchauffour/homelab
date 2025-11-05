.PHONY: template deploy undeploy redeploy

diff:
	helmfile diff
template:
	helmfile template
deploy:
	helmfile apply
undeploy:
	helmfile destroy
redeploy: undeploy deploy
