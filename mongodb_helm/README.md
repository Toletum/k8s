##########################
helm create mi-chart


rm -v mi-chart/templates/*.yaml
cp mongodb-daemonsets.yaml init-rs-job.yaml mi-chart/templates/
cp values.yaml mi-chart/


helm template mi-release mi-chart
helm install mi-release mi-chart




