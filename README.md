# COSC-5610 (Advanced Networking): BMv2 and P4C Setup
```
Instructor: Prof. Benjamin E. Ujcich (bu31@georgetown.edu)
TA: Dhiraj Saharia (ds1849@georgetown.edu)
```

This document describes a Linux-based environment for compiling and running a
P4 program with the BMv2 `simple_switch` target. Docker is used for the P4
toolchain and BMv2; Mininet runs inside the same privileged container so that
it can create network namespaces and virtual Ethernet links.

The exercise uses the standard P4 tutorial basic-forwarding design, adapted to
a two-host topology and the BMv2 Thrift CLI. A second example will be added in
a later exercise.

## 1. Background

The setup contains several components, each with a distinct role in the
experiment:

- **P4 program (`basic.p4`)** — defines the packet-processing behavior of the
  switch. It specifies how packets are parsed, how the IPv4 forwarding table
  is applied, how Ethernet addresses are rewritten, and how packets are
  transmitted.
- **P4C** — the P4 compiler. It translates `basic.p4` into BMv2's JSON
  representation, `build/basic.json`. This file describes the compiled data
  plane that BMv2 will execute.
- **BMv2** — the Behavioral Model version 2 software switch. It emulates a
  programmable network switch in *software*. This exercise uses its
  `simple_switch` target and the v1model architecture. There are different targets such as ASIC (Tofino-based), SoC (Nvidia BlueField SmartNICs), FPGA (NetFPGA), etc.
- **`simple_switch`** — the BMv2 executable that loads and runs
  `build/basic.json`. It connects switch ports to Linux network interfaces and
  processes packets according to the compiled P4 program. It is entirely done in software and convenient for prototyping and proof-of-concept implementations. This acts as the *data-plane* of the network.
- **Thrift CLI** — the control-plane interface used to install table entries
  into `simple_switch`. The commands in `commands.txt` associate destination
  IPv4 addresses with next-hop MAC addresses and output ports. Think of it as the *control-plane* of the network.
- **Mininet** — creates a small emulated network using Linux network
  namespaces and virtual Ethernet pairs. In this exercise, it creates hosts
  `h1` and `h2`, connects them to `s1`, and provides the `mininet>` command
  prompt. This is used to emulate standard linux systems as network nodes to send packets, capture traffic, emulate host behavior etc.
- **Docker** — provides a repeatable environment containing P4C, BMv2,
  Mininet, and their dependencies. The container is privileged (**sudo**) because
  Mininet must create network namespaces and virtual Ethernet devices.

The main workflow is:

```text
basic.p4 --(p4c)--> build/basic.json --(simple_switch)--> BMv2 data plane
                                      ^
commands.txt --(Thrift CLI)----------| table entries

Mininet supplies the hosts, links, and interfaces connected to simple_switch.
```

P4C creates the data-plane program, while the Thrift CLI supplies the
control-plane table entries. Both are required: the P4 program defines what
the switch can do, and the table entries determine how the switch handles the
specific destinations in this topology.

## 2. Prerequisites

Use a 64-bit Linux system with:

- Docker Engine
- Docker Compose v2 (`docker compose`)
- At least 4 GB of memory available to Docker
- Internet access while building the image

This repository was tested on a system with the following configurations:
- OS: Ubuntu 22.04.5 LTS
- Kernel: 5.15.0-143-generic
- CPU: Intel Xeon E5-2640 v4 (40) @ 3.400GHz

Any standard Linux system should be good enough.

Verify the installation on the host:

```bash
docker --version
docker compose version
```

If Docker requires administrator privileges on your system, either prefix the
commands below with `sudo` or configure the student account to use Docker.

## 3. Build the laboratory image

From this directory, build the image:

```bash
docker compose build
```

The image contains:

- `p4c` for compiling P4_16 programs;
- BMv2 `simple_switch` with its Thrift control interface;
- Mininet and the standard Linux networking utilities.

The image is based on the official `p4lang/p4c` image. BMv2 is built with
Thrift support and without P4Runtime because this exercise uses
`simple_switch` and its Thrift CLI.

## 4. Start the container

Start an interactive shell in the laboratory container:

```bash
docker compose run --rm p4lab bash
```

The current directory is mounted at `/workspace` inside the container. The
following commands are therefore executed inside the container unless stated
otherwise.

Confirm that the required programs are available:

```bash
p4c --version
simple_switch --help | head
python3 --version
mn --version
```

## 5. Compile and run basic forwarding

Compile the P4 program and start the Mininet topology:

```bash
make run
```

The command performs two operations:

1. It compiles `basic.p4` for BMv2's v1model architecture and writes
   `build/basic.json`.
2. It starts one BMv2 `simple_switch` connected to two Mininet hosts and
   installs two IPv4 forwarding entries through the Thrift CLI.

The topology is:

```text
h1 (10.0.1.1/24) ---- port 1  s1  port 2 ---- h2 (10.0.2.2/24)
```

At the `mininet>` prompt, test forwarding:

```text
mininet> h1 ping -c 3 h2
mininet> h2 ping -c 3 h1
```

Both commands should complete successfully. The switch program performs the
following operations for IPv4 packets:

- lookup on `hdr.ipv4.dstAddr` using an LPM table;
- rewrite the Ethernet source and destination addresses;
- decrement the IPv4 TTL;
- transmit the packet on the selected egress port.

Inspect the installed table entries if desired:

```text
mininet> sh echo "table_dump ipv4_lpm" | simple_switch_CLI --thrift-port 9090
```

Exit Mininet and clean generated files:

```text
mininet> exit
```

```bash
make clean
exit
```

The final `exit` leaves the container. The generated build files, logs, and
pcaps are stored in this directory because it is mounted into the container.

## 6. Files in this directory

- `basic.p4` — complete P4_16 basic-forwarding program.
- `commands.txt` — Thrift CLI commands installed into `s1`.
- `run_mininet.py` — two-host Mininet runner for BMv2 `simple_switch`.
- `Makefile` — compile, run, and cleanup commands.
- `Dockerfile` — image definition for `p4c`, BMv2, and Mininet.
- `compose.yaml` — privileged container configuration required by Mininet.

## 7. Troubleshooting

### Docker build fails because of memory

Allocate at least 4 GB of memory to Docker and retry:

```bash
docker compose build --no-cache
```

### Mininet reports a permissions error

Mininet requires network namespaces and virtual Ethernet devices. Start the
container through `docker compose run --rm p4lab bash`; the Compose file marks
the container as privileged. Do not start this exercise with a plain
unprivileged `docker run` command.

### A previous run left Mininet state behind

Inside the container, run:

```bash
mn -c
make run
```

### The ping fails

Check that the switch table entries were installed and that the BMv2 log does
not report an interface or Thrift error:

```bash
cat logs/s1.log
simple_switch_CLI --thrift-port 9090
```

At the CLI prompt, `table_dump ipv4_lpm` should show entries for `10.0.1.1/32`
and `10.0.2.2/32`.

## References

- [P4 tutorial: Basic Forwarding](https://github.com/p4lang/tutorials/tree/master/exercises/basic)
- [P4C BMv2 compilation](https://hub.docker.com/r/p4lang/p4c)
- [BMv2 Simple Switch](https://github.com/p4lang/behavioral-model/blob/main/docs/simple_switch.md)
