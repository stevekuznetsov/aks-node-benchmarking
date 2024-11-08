#!/usr/bin/env bash

set -o errexit
set -o nounset
set -o pipefail
set -o xtrace

mkdir -p _output/logs

cleanup() {
  for child in $( jobs -p ); do
    kill "${child}"
    wait "${child}"
  done
  wait
}
trap cleanup EXIT

while true; do
	pods="$( kubectl --kubeconfig "${KUBECONFIG}" --namespace kube-system get pods --selector component=kubelet-parameters -o yaml )"
	for pod in $( yq '.items[].metadata.name' <<<"${pods}" ); do
		node="$( yq '.items[] | select(.metadata.name=="'"${pod}"'") | .spec.nodeName' <<<"${pods}" )"
		mkdir -p "_output/logs/${node}/"
		if [[ ! -s "_output/logs/${node}/${pod}.log" ]]; then
			kubectl --kubeconfig "${KUBECONFIG}" --namespace kube-system logs "pod/${pod}" -f > "_output/logs/${node}/${pod}.log" &
		fi
	done
done