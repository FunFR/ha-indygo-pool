FROM mcr.microsoft.com/devcontainers/python:3.12@sha256:dc5aa4f3498281ac9f833eb9627b607eb8aa37b1aa1b5953524808d4894a6031

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
