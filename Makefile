_output/:
	mkdir -p _output/

_output/kubeconfig: _output/
	az login --tenant 93b21e64-4824-439a-b893-46c9b2a51082 --subscription 403d9de9-132b-4974-94a5-5b78bdfa191e
	az aks get-credentials --resource-group perf-scale-rg --name aks-cluster-001 --file _output/kubeconfig

.PHONY: daemonset
daemonset: _output/kubeconfig
	kubectl --kubeconfig _output/kubeconfig apply -f daemonset.yaml

.PHONY: pods
pods: _output/kubeconfig
	kubectl --kubeconfig _output/kubeconfig --namespace kube-system get pods --selector component=kubelet-parameters -o wide

.PHONY: logs
logs: _output/kubeconfig daemonset
	KUBECONFIG=_output/kubeconfig ./logs.sh