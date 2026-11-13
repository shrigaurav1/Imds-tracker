import subprocess

class Firewall:
    CHAIN, HOOKS = "IMDS_TRACK", ("PREROUTING", "OUTPUT")
    def __init__(self, ip, iptables="iptables", nsenter="nsenter"):
        self.ip, self.iptables, self.nsenter = ip, iptables, nsenter
    def run(self, *args):
        cmd = [self.nsenter, "-t", "1", "-m", "-n", "--", self.iptables, "-w", "-t", "raw", *args]
        return subprocess.run(cmd, capture_output=True, text=True)
    def jump(self, hook): return [hook, "-d", self.ip + "/32", "-p", "tcp", "--dport", "80", "-j", self.CHAIN]
    def install(self):
        ok = True
        created = self.run("-N", self.CHAIN)
        if created.returncode and "already exists" not in created.stderr.lower():
            print("chain create failed: " + created.stderr.strip(), flush=True); ok = False
        if self.run("-F", self.CHAIN).returncode: ok = False
        rules = [
            (["-m","string","--algo","bm","--string","PUT /latest/api/token"], "IMDS_TOKEN: ", True),
            (["-m","string","--algo","bm","--icase","--string","x-aws-ec2-metadata-token:"], "IMDS_V2: ", True),
            (["-m","string","--algo","bm","--string","GET /"], "IMDS_V1: ", False),
        ]
        for matcher, prefix, add_return in rules:
            if self.run("-A", self.CHAIN, *matcher, "-j", "LOG", "--log-prefix", prefix).returncode: ok = False
            if add_return and self.run("-A", self.CHAIN, *matcher, "-j", "RETURN").returncode: ok = False
        for hook in self.HOOKS:
            if self.run("-C", *self.jump(hook)).returncode and self.run("-I", *self.jump(hook)).returncode: ok = False
        print(f"iptables rules installed ok={ok}", flush=True)
        return int(ok)
    def cleanup(self):
        for hook in self.HOOKS:
            while self.run("-D", *self.jump(hook)).returncode == 0: pass
        self.run("-F", self.CHAIN); self.run("-X", self.CHAIN)
        print("iptables rules removed", flush=True)
