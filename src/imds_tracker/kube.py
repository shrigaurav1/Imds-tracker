import json, os, re, ssl, threading, time, urllib.parse, urllib.request

class PodResolver:
    def __init__(self, node_name, refresh_seconds=30):
        self.node_name, self.refresh_seconds = node_name, refresh_seconds
        self.lock, self.pods, self.last_refresh = threading.Lock(), {}, 0.0

    @staticmethod
    def workload_name(pod):
        meta = pod.get("metadata", {})
        owners = meta.get("ownerReferences") or []
        if not owners: return meta.get("name", "unknown")
        kind, name = owners[0].get("kind", ""), owners[0].get("name", "unknown")
        if kind == "ReplicaSet":
            labels = meta.get("labels", {})
            h = labels.get("pod-template-hash") or labels.get("rollouts-pod-template-hash")
            if h and name.endswith("-" + h): name = name[: -len(h)-1]
        elif kind == "Job":
            name = re.sub(r"-\\d{8,}$", "", name)
        return name

    def refresh(self):
        sa = "/var/run/secrets/kubernetes.io/serviceaccount"
        host = os.environ.get("KUBERNETES_SERVICE_HOST")
        port = os.environ.get("KUBERNETES_SERVICE_PORT", "443")
        if not host: raise RuntimeError("KUBERNETES_SERVICE_HOST is not set")
        with open(sa + "/token", encoding="utf-8") as f: token = f.read().strip()
        ctx = ssl.create_default_context(cafile=sa + "/ca.crt")
        selector = urllib.parse.quote("spec.nodeName=" + self.node_name, safe="")
        req = urllib.request.Request(f"https://{host}:{port}/api/v1/pods?fieldSelector={selector}",
                                     headers={"Authorization": "Bearer " + token})
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response: data = json.load(response)
        updated = {}
        for pod in data.get("items", []):
            if pod.get("spec", {}).get("hostNetwork"): continue
            ip = pod.get("status", {}).get("podIP")
            if ip: updated[ip] = (self.workload_name(pod), pod.get("metadata", {}).get("namespace", "unknown"))
        with self.lock: self.pods, self.last_refresh = updated, time.time()

    def resolve(self, ip, node_ip):
        if node_ip and ip == node_ip: return "host-network", "host"
        with self.lock: result, stale = self.pods.get(ip), time.time() - self.last_refresh > self.refresh_seconds
        if result is None and stale:
            try: self.refresh()
            except Exception as exc: print(f"pod cache refresh failed: {exc}", flush=True)
            with self.lock: result = self.pods.get(ip)
        return result or ("unknown", "unknown")

    def run(self, stop):
        while not stop.is_set():
            try: self.refresh()
            except Exception as exc: print(f"pod cache refresh failed: {exc}", flush=True)
            stop.wait(self.refresh_seconds)
