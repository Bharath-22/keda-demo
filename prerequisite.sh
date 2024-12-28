#!/bin/bash

#To install Helm
curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3
chmod 700 get_helm.sh
./get_helm.sh

pip3 install flask
pip3 install kubernetes
pip3 install pyyaml