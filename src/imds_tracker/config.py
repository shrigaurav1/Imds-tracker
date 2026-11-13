import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    node_name: str
    node_ip: str
    metrics_port: int
    imds_ip: str
    pod_refresh_seconds: int
    iptables_bin: str
    nsenter_bin: str

    @classmethod
    def from_env(cls):
        port = int(os.getenv("METRICS_PORT", "9877"))
        if not 1 <= port <= 65535:
            raise ValueError("METRICS_PORT must be between 1 and 65535")
        return cls(os.getenv("NODE_NAME", "unknown"), os.getenv("NODE_IP", ""), port,
                   os.getenv("IMDS_IP", "169.254.169.254"),
                   max(5, int(os.getenv("POD_REFRESH_SECONDS", "30"))),
                   os.getenv("IPTABLES_BIN", "iptables"), os.getenv("NSENTER_BIN", "nsenter"))
