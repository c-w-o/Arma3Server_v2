FROM debian:bookworm-slim

LABEL maintainer="CWO - github.com/c-w-o"
LABEL org.opencontainers.image.source="https://github.com/c-w-o/arma3server_v2"

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update \
  && apt-get install -y --no-install-recommends --no-install-suggests \
      python3 \
      python3-pip \
      python3-venv \
      curl \
      lib32stdc++6 \
      lib32gcc-s1 \
      libcurl4 \
      iputils-ping \
      net-tools \
      wget \
      ca-certificates \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv \
  && /opt/venv/bin/python -m pip install --no-cache-dir --upgrade \
      pip setuptools wheel \
  && /opt/venv/bin/pip install --no-cache-dir \
      json5 jsonschema \
      fastapi uvicorn \
      pydantic pydantic-settings \
      pytest pytest-cov httpx \
      python-dotenv
      
ENV PATH="/opt/venv/bin:${PATH}"

RUN mkdir -p /steamcmd \
  && cd /steamcmd \
  && wget -q https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz \
  && tar -xzf steamcmd_linux.tar.gz \
  && rm -f steamcmd_linux.tar.gz \
  && chmod +x /steamcmd/steamcmd.sh || true

ENV ARMA_ROOT=/arma3
ENV COMMON_SHARE_ARMA_ROOT=/var/run/share/arma3/server-common
ENV THIS_SHARE_ARMA_ROOT=/var/run/share/arma3/this-server
ENV TMP_DIR=/tmp
ENV PYTHONPATH=/launcher

# Workshop cache (code uses TMP_DIR/steamapps/workshop/content/107410)
RUN mkdir -p \
      "${ARMA_ROOT}" \
      "${COMMON_SHARE_ARMA_ROOT}" \
      "${THIS_SHARE_ARMA_ROOT}" \
      "${TMP_DIR}/steamapps/workshop/content/107410" 

WORKDIR /tmp

COPY launcher /launcher/

EXPOSE 2302/udp 2303/udp 2304/udp 2305/udp 2306/udp 8000/tcp

STOPSIGNAL SIGINT

ENTRYPOINT ["python3", "/launcher/launcher.py"]
