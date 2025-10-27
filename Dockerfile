FROM debian:bullseye-slim

LABEL maintainer="CWO - github.com/c-w-o"
LABEL org.opencontainers.image.source=https://github.com/c-w-o/arma3server_v2

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN apt-get update \
    && \
    apt-get install -y --no-install-recommends --no-install-suggests \
        python3 \
        python3-pip \
        net-tools \
        nano \
        curl \
	    iputils-ping \
        lib32stdc++6 \
        lib32gcc-s1 \
        libcurl4 \
        wget \
        ca-certificates \
    && \
    pip install json5 jsonschema \
    && \
    apt-get remove --purge -y \
    && \
    apt-get clean autoclean \
    && \
    apt-get autoremove -y \
    && \
    rm -rf /var/lib/apt/lists/* 

RUN mkdir -p /steamcmd && \
    cd /steamcmd && \
    wget https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz && \
    tar -xvzf steamcmd_linux.tar.gz && \
    rm steamcmd_linux.tar.gz


ENV ARMA_ROOT=/arma3
ENV COMMON_SHARE_ARMA_ROOT=/var/run/share/arma3/server-common
ENV THIS_SHARE_ARMA_ROOT=/var/run/share/arma3/this-server
ENV WORKSHOP_DIR=/tmp/steamapps/workshop/content/107410

RUN mkdir -p $ARMA_ROOT $COMMON_SHARE_ARMA_ROOT $THIS_SHARE_ARMA_ROOT $WORKSHOP_DIR
WORKDIR /arma3



EXPOSE 2302/udp 2303/udp 2304/udp 2305/udp 2306/udp


STOPSIGNAL SIGINT
COPY launcher /launcher/
ENTRYPOINT ["python3", "/launcher/launcher.py"]
