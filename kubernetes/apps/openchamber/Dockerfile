FROM ghcr.io/anomalyco/opencode:latest

USER root

RUN apk add --no-cache \
    bash \
    git \
    neovim \
    openssh-client \
    github-cli \
    delta \
    pre-commit \
    kubectl \
    curl \
    unzip

# Build dependencies for node-pty native module
RUN apk add --no-cache --virtual .build-deps build-base

RUN addgroup -g 1000 openchamber && \
    adduser -D -u 1000 -G openchamber -h /home/openchamber -s /bin/bash openchamber

USER 1000
ENV HOME=/home/openchamber

RUN mkdir -p /home/openchamber/.local/state /home/openchamber/.local/share/opencode/worktree /home/openchamber/.config/opencode
RUN curl -fsSL https://bun.sh/install | bash

ENV PATH="/home/openchamber/.bun/bin:/home/openchamber/bin:$PATH"
ENV BUN_INSTALL_BIN=/home/openchamber/bin

RUN bun add --trust -g @openchamber/web

# Remove build dependencies
USER root
RUN apk del .build-deps
RUN ln -s /home/openchamber/.bun/bin/bun /usr/local/bin/node

USER 1000
WORKDIR /projects
