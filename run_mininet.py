#!/usr/bin/env python3

import argparse
import os
import shutil
import signal
import subprocess
import sys
import time

from mininet.cli import CLI
from mininet.log import error, info, setLogLevel
from mininet.net import Mininet
from mininet.node import Host, Switch
from mininet.topo import Topo


class P4Host(Host):
    """Mininet host with a stable interface name for the exercise."""

    def config(self, **params):
        result = super().config(**params)
        self.defaultIntf().rename("eth0")
        for offload in ("rx", "tx", "sg"):
            self.cmd(f"ethtool --offload eth0 {offload} off")
        self.cmd("sysctl -w net.ipv6.conf.all.disable_ipv6=1")
        self.cmd("sysctl -w net.ipv6.conf.default.disable_ipv6=1")
        self.cmd("sysctl -w net.ipv6.conf.lo.disable_ipv6=1")
        return result


class P4Switch(Switch):
    """Mininet switch wrapper for BMv2 simple_switch."""

    def __init__(self, name, sw_path, json_path, thrift_port, log_file, **kwargs):
        super().__init__(name, **kwargs)
        self.sw_path = sw_path
        self.json_path = json_path
        self.thrift_port = thrift_port
        self.log_file = log_file
        self.process = None
        self.log_handle = None

    def start(self, controllers):
        args = [self.sw_path]
        for port, intf in self.intfs.items():
            if intf and intf.link and not intf.IP():
                args.extend(["-i", f"{port}@{intf.name}"])
        args.extend([
            "--thrift-port", str(self.thrift_port),
            "--device-id", "0",
            "--log-console",
            self.json_path,
        ])
        info("Starting BMv2: " + " ".join(args) + "\n")
        self.log_handle = open(self.log_file, "w", encoding="utf-8")
        self.process = self.popen(
            args, stdout=self.log_handle, stderr=subprocess.STDOUT
        )
        time.sleep(1)
        if self.process.poll() is not None:
            raise RuntimeError(f"BMv2 exited early; inspect {self.log_file}")

    def stop(self, deleteIntfs=True):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
        if self.log_handle is not None:
            self.log_handle.close()
        super().stop(deleteIntfs=deleteIntfs)


class TwoHostTopo(Topo):
    def build(self, switch_cls, switch_json, log_file):
        self.addHost("h1", ip="10.0.1.1/24", mac="08:00:00:00:01:11")
        self.addHost("h2", ip="10.0.2.2/24", mac="08:00:00:00:02:22")
        self.addSwitch(
            "s1",
            cls=switch_cls,
            sw_path="simple_switch",
            json_path=switch_json,
            thrift_port=9090,
            log_file=log_file,
        )
        self.addLink("h1", "s1", port2=1)
        self.addLink("h2", "s1", port2=2)


def find_cli():
    for name in ("simple_switch_CLI", "runtime_CLI", "bm_CLI"):
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError("Could not find a BMv2 Thrift CLI")


def install_commands(cli_path, switch_json, commands_path):
    command = [cli_path, "--thrift-port", "9090"]
    if os.path.basename(cli_path) == "runtime_CLI":
        command.extend(["--json", switch_json])
    with open(commands_path, "r", encoding="utf-8") as commands_file:
        result = subprocess.run(
            command,
            stdin=commands_file,
            text=True,
            capture_output=True,
            check=False,
        )
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    if result.returncode != 0:
        raise RuntimeError("The BMv2 Thrift CLI could not install the table entries")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--switch-json", required=True)
    parser.add_argument("--commands", required=True)
    parser.add_argument("--log-dir", default="logs")
    args = parser.parse_args()

    os.makedirs(args.log_dir, exist_ok=True)
    topo = TwoHostTopo(
        switch_cls=P4Switch,
        switch_json=os.path.abspath(args.switch_json),
        log_file=os.path.abspath(os.path.join(args.log_dir, "s1.log")),
    )
    net = Mininet(
        topo=topo,
        host=P4Host,
        controller=None,
        build=False,
        autoSetMacs=False,
    )

    try:
        net.start()

        h1, h2 = net.get("h1", "h2")
        h1.cmd("ip route replace 10.0.2.0/24 via 10.0.1.10 dev eth0")
        h2.cmd("ip route replace 10.0.1.0/24 via 10.0.2.20 dev eth0")
        h1.cmd("arp -s 10.0.1.10 08:00:00:00:01:00")
        h2.cmd("arp -s 10.0.2.20 08:00:00:00:02:00")

        cli_path = find_cli()
        install_commands(cli_path, os.path.abspath(args.switch_json), args.commands)

        print("\nBMv2 is running. Use the Mininet prompt to test h1 and h2.\n")
        CLI(net)
    finally:
        net.stop()


if __name__ == "__main__":
    setLogLevel("info")
    try:
        main()
    except KeyboardInterrupt:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        sys.exit(130)
    except Exception as exc:
        error(str(exc) + "\n")
        sys.exit(1)
