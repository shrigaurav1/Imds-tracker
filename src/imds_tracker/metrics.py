import threading
from collections import defaultdict


def esc(value):
    return (str(value).replace("\\", "\\\\")
            .replace("\n", "\\n").replace('"', '\\"'))


class Metrics:
    def __init__(self, node):
        self.node = node
        self.lock = threading.Lock()
        self.counts = defaultdict(int)
        self.rules = 0

    def increment(self, workload, namespace, version):
        with self.lock:
            self.counts[(workload, namespace, version)] += 1

    def set_rules(self, value):
        with self.lock:
            self.rules = int(value)

    def render(self):
        with self.lock:
            items = list(self.counts.items())
            rules = self.rules
        out = [
            "# HELP imds_requests_total HTTP requests to IMDS observed on this node",
            "# TYPE imds_requests_total counter",
        ]
        for (workload, namespace, version), count in sorted(items):
            labels = (
                f'source_workload="{esc(workload)}",'
                f'source_namespace="{esc(namespace)}",'
                f'version="{esc(version)}",node="{esc(self.node)}"'
            )
            out.append(f"imds_requests_total{{{labels}}} {count}")
        out.extend([
            "# HELP imds_tracker_rules_installed 1 if iptables rules were installed",
            "# TYPE imds_tracker_rules_installed gauge",
            f'imds_tracker_rules_installed{{node="{esc(self.node)}"}} {rules}',
            "# HELP imds_tracker_up 1 while exporter is serving",
            "# TYPE imds_tracker_up gauge",
            f'imds_tracker_up{{node="{esc(self.node)}"}} 1',
        ])
        return "\n".join(out) + "\n"
