# Kubernetes IMDS Tracker

A Kubernetes DaemonSet that observes IPv4 HTTP requests to the EC2 Instance Metadata Service (IMDS) and exports per-workload counters in Prometheus text exposition format.

**Monitoring compatibility:** Prometheus, VictoriaMetrics, and any scraper supporting Prometheus exposition can scrape `/metrics`.

## Metrics

- `imds_requests_total{source_workload,source_namespace,version,node}` — observed requests; `version` is `v1`, `v2`, or `token`.
- `imds_tracker_rules_installed{node}` — 1 when all iptables rules were installed, otherwise 0.
- `imds_tracker_up{node}` — exporter process health.

ReplicaSet pods are grouped under their Deployment name. Other pods use their first owner name. Host-network traffic is grouped as `host-network`; unresolved/deleted pods are `unknown`.

## Layout

```text
src/imds_tracker/   # separate Python modules
  config.py firewall.py kube.py metrics.py reader.py main.py
  __init__.py
docker/             # Debian recommended, Alpine alternative, debug image
manifests/          # namespace, RBAC, DaemonSet, Service, optional scraper CRs
```

## Build and deploy

```bash
docker build -f docker/Dockerfile.debian -t YOUR_REGISTRY/kubernetes-imds-tracker:0.1.0 .
docker push YOUR_REGISTRY/kubernetes-imds-tracker:0.1.0
```

For multi-arch:

```bash
docker buildx build --platform linux/amd64,linux/arm64 \\
  -f docker/Dockerfile.debian -t YOUR_REGISTRY/kubernetes-imds-tracker:0.1.0 --push .
```

Edit `manifests/02-daemonset.yaml` and set the image. Example namespace is `imds-system`.
Apply core resources:

```bash
kubectl apply -f manifests/00-namespace.yaml
kubectl apply -f manifests/01-rbac.yaml
kubectl apply -f manifests/02-daemonset.yaml
kubectl apply -f manifests/03-service.yaml
kubectl -n imds-system rollout status ds/imds-tracker
```

Test from a host or a network-reachable pod using a node IP:

```bash
curl http://NODE_IP:9877/healthz
curl http://NODE_IP:9877/metrics
```

### Prometheus Operator

If installed, apply `manifests/10-servicemonitor.yaml`. Adjust its `release` label and ensure the Prometheus instance selects the ServiceMonitor namespace and labels.

### VictoriaMetrics Operator

If installed, apply `manifests/11-vmservicescrape.yaml`. Ensure your VMAgent/VMCluster selects its labels and namespace.

## Configuration

| Environment variable | Default | Purpose |
|---|---:|---|
| `METRICS_PORT` | `9877` | HTTP listen port |
| `NODE_NAME` | injected | Node name from `spec.nodeName` |
| `NODE_IP` | injected | Node IP from `status.hostIP` |
| `POD_REFRESH_SECONDS` | `30` | Pod-IP cache refresh interval (minimum 5) |
| `IMDS_IP` | `169.254.169.254` | IMDS IPv4 address |
| `IPTABLES_BIN` | `iptables` | iptables executable in image |
| `NSENTER_BIN` | `nsenter` | nsenter executable in image |

**Port changes:** update `METRICS_PORT`, `containerPort`, and Service `port`/`targetPort` consistently. The DaemonSet uses `hostNetwork: true`, so the port must be free on every node. Changing only the Service port does not change the process listener.

## Example PromQL

```promql
sum by (source_namespace, source_workload, version) (rate(imds_requests_total[5m]))
```

```promql
sum by (source_namespace, source_workload) (increase(imds_requests_total{version="v1"}[1h]))
```

## Important limitations and security

- This is best-effort packet observation, not an authoritative audit log. It matches HTTP request strings in IPv4 TCP packets to IMDS on port 80. TLS-encrypted/non-matching traffic is not decoded.
- iptables string matching can miss requests if the matching text is segmented across packets. Treat counters as operational visibility, not security-grade accounting.
- `LOG` writes to the kernel log; `/dev/kmsg` access and kernel logging behavior vary by node OS/kernel.
- The iptables binary/backend in the container must be compatible with the host's nftables/legacy setup. Validate on your node image.
- Host-network pods share the node IP and cannot be attributed to a specific pod by source IP.
- The DaemonSet is privileged, uses host PID/network namespaces, reads `/dev/kmsg`, and modifies host iptables. Review the manifest, pin/scan images, and restrict RBAC before production use.
- This tool observes IMDS traffic; it does not enforce IMDSv2 or change EC2 metadata options. Enforce IMDSv2 separately after application compatibility testing.

## Troubleshooting

- `iptables rules installed=0`: inspect logs, iptables backend, and host permissions.
- No metrics: check pod status, port conflicts, `METRICS_PORT`, and probes.
- `unknown` workload labels: check service-account token mounting, RBAC, API connectivity, and pod cache logs.
- No counters: confirm IPv4 TCP/80 traffic to the configured IMDS IP and inspect kernel logs for `IMDS_V1`, `IMDS_V2`, and `IMDS_TOKEN`.

MIT licensed. Contributions welcome; include sanitized logs, node OS/kernel, Kubernetes version, and iptables backend in bug reports.
