import signal
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .config import Config
from .firewall import Firewall
from .kube import PodResolver
from .metrics import Metrics
from .reader import KernelLogReader


def main():
    cfg = Config.from_env()
    stop = threading.Event()
    metrics = Metrics(cfg.node_name)
    resolver = PodResolver(cfg.node_name, cfg.pod_refresh_seconds)
    firewall = Firewall(cfg.imds_ip, cfg.iptables_bin, cfg.nsenter_bin)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/healthz":
                status, body, content_type = 200, b"ok\n", "text/plain; charset=utf-8"
            elif self.path == "/metrics":
                status, body, content_type = 200, metrics.render().encode(), "text/plain; version=0.0.4; charset=utf-8"
            else:
                status, body, content_type = 404, b"not found\n", "text/plain; charset=utf-8"
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            return

    server = ThreadingHTTPServer(("0.0.0.0", cfg.metrics_port), Handler)
    server.daemon_threads = True

    def handle_signal(signum, _frame):
        print(f"received signal {signum}; shutting down", flush=True)
        stop.set()
        # shutdown() must run outside the serve_forever thread.
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    metrics.set_rules(firewall.install())
    threading.Thread(target=resolver.run, args=(stop,), daemon=True, name="pod-resolver").start()
    reader = KernelLogReader(resolver, metrics, cfg.node_ip)
    threading.Thread(target=reader.run, args=(stop,), daemon=True, name="kernel-reader").start()

    print(f"IMDS tracker listening on :{cfg.metrics_port} node={cfg.node_name}", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    finally:
        server.server_close()
        stop.set()
        firewall.cleanup()


if __name__ == "__main__":
    main()
