FROM p4lang/p4c:latest

USER root

ARG BMV2_VERSION=1.15.2
ARG MININET_VERSION=2.3.0

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        automake \
        build-essential \
        ca-certificates \
        cmake \
        ethtool \
        flex \
        bison \
        git \
        help2man \
        iproute2 \
        iputils-ping \
        libboost-dev \
        libboost-filesystem-dev \
        libboost-program-options-dev \
        libboost-system-dev \
        libboost-test-dev \
        libboost-thread-dev \
        libevent-dev \
        libgmp-dev \
        libpcap-dev \
        libssl-dev \
        libtool \
        libthrift-dev \
        net-tools \
        pkg-config \
        procps \
        psmisc \
        python3 \
        python3-pip \
        thrift-compiler \
        tcpdump \
    && rm -rf /var/lib/apt/lists/*

# The Ubuntu "mininet" package only provides a Python 2 module (mn itself is
# a python2 script on this base image), but run_mininet.py requires Python 3
# mininet. Mininet 2.3.0+ supports Python 3, so it is built from source here.
RUN git clone --depth 1 --branch "${MININET_VERSION}" \
        https://github.com/mininet/mininet.git /tmp/mininet \
    && PYTHON=python3 make -C /tmp/mininet install \
    && rm -rf /tmp/mininet

RUN git clone --depth 1 --branch "${BMV2_VERSION}" \
        https://github.com/p4lang/behavioral-model.git /tmp/behavioral-model \
    && cmake -S /tmp/behavioral-model -B /tmp/behavioral-model-build \
        -DCMAKE_BUILD_TYPE=Release \
        -DWITH_NANOMSG=OFF \
        -DWITH_PI=OFF \
        -DWITH_THRIFT=ON \
        -DWITH_TARGETS=ON \
        -DENABLE_MODULES=OFF \
    && cmake --build /tmp/behavioral-model-build --parallel "$(nproc)" \
    && cmake --install /tmp/behavioral-model-build \
    && rm -rf /tmp/behavioral-model /tmp/behavioral-model-build

WORKDIR /workspace

CMD ["bash"]
