import os
import re

PATTERN = re.compile(r"IMDS_(V1|V2|TOKEN): .*?SRC=(\d{1,3}(?:\.\d{1,3}){3})")


class KernelLogReader:
    def __init__(self, resolver, metrics, node_ip):
        self.resolver = resolver
        self.metrics = metrics
        self.node_ip = node_ip

    def run(self, stop):
        fd = os.open("/dev/kmsg", os.O_RDONLY)
        try:
            os.lseek(fd, 0, os.SEEK_END)
            print("listening on /dev/kmsg", flush=True)
            while not stop.is_set():
                record = os.read(fd, 8192).decode("utf-8", errors="ignore")
                match = PATTERN.search(record)
                if match:
                    version, source_ip = match.group(1).lower(), match.group(2)
                    workload, namespace = self.resolver.resolve(source_ip, self.node_ip)
                    self.metrics.increment(workload, namespace, version)
        finally:
            os.close(fd)
