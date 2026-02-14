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
    kubectl

RUN addgroup -g 1000 opencode && \
    adduser -D -u 1000 -G opencode -h /home/opencode -s /bin/bash opencode

USER 1000
RUN mkdir -p /home/opencode/.local/state /home/opencode/.local/share/opencode/worktree
WORKDIR /projects
