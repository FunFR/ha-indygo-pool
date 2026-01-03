FROM mcr.microsoft.com/devcontainers/python:3.12

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install HA requirements
RUN apt-get update && apt-get install -y --no-install-recommends \
    libudev-dev \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libswscale-dev \
    libswresample-dev \
    libavfilter-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

WORKDIR /workspaces/indygo-pool
