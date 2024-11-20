_output/:
	mkdir -p _output/

_output/tenant: _output/
	az account show --query tenantId --output tsv > $@

_output/subscription: _output/
	az account show --query id --output tsv > $@

_output/kubeconfig: _output/ _output/tenant _output/subscription
	yes | az login --tenant 93b21e64-4824-439a-b893-46c9b2a51082
	az account set --subscription 403d9de9-132b-4974-94a5-5b78bdfa191e
	az aks get-credentials --resource-group perf-scale-rg --name aks-cluster-001 --file _output/kubeconfig
	yes | az login --tenant $(shell cat _output/tenant)
	az account set --subscription $(shell cat _output/subscription)

_output/daemonset.yaml: _output/kubeconfig
	kubectl --kubeconfig _output/kubeconfig apply -f daemonset.yaml -o yaml > $@

_output/pods: _output/kubeconfig
	kubectl --kubeconfig _output/kubeconfig --namespace kube-system get pods --selector component=kubelet-parameters -o wide | tee $@

_output/logs: _output/kubeconfig _output/daemonset.yaml
	KUBECONFIG=_output/kubeconfig ./logs.sh

_output/parca.yaml: _output/
	wget --no-use-server-timestamps --quiet --output-document=$@ https://github.com/parca-dev/parca/releases/download/v0.22.0/kubernetes-manifest.yaml
	touch $@

_output/parca-deployment.yaml: _output/parca.yaml
	# TODO: split into separate lines using yq --inplace
	# TODO: add resource requests to parca
	# TODO: set flags for parca to store more history
	yq 'select(.kind=="Deployment") | .spec.template.spec.nodeSelector.agentpool = "agentpool" | .spec.template.spec.tolerations = [{"key": "CriticalAddonsOnly", "operator": "Exists"}]' <_output/parca.yaml > $@

_output/parca-extra.yaml: _output/parca.yaml
	yq 'select(.kind=="Deployment" | not)' <_output/parca.yaml > $@

_output/parca-agent.yaml: _output/
	wget --no-use-server-timestamps --quiet --output-document=$@ https://github.com/parca-dev/parca-agent/releases/download/v0.35.0/kubernetes-manifest.yaml
	touch $@

_output/parca: _output/kubeconfig _output/parca-deployment.yaml _output/parca-extra.yaml _output/parca-agent.yaml
	kubectl --kubeconfig _output/kubeconfig --namespace parca apply -f _output/parca-extra.yaml
	kubectl --kubeconfig _output/kubeconfig --namespace parca apply -f _output/parca-deployment.yaml
	kubectl --kubeconfig _output/kubeconfig --namespace parca apply -f _output/parca-agent.yaml
	touch _output/parca