FROM registry.fedoraproject.org/fedora-minimal:42

RUN dnf5 install -y \
        python3 \
        python3-pip \
        ffmpeg \
        file-libs \
    && dnf5 clean all -y

WORKDIR /src
COPY pyproject.toml MANIFEST.in README.md ./
COPY .config ./.config
COPY src ./src
RUN pip3 install --root-user-action=ignore .

WORKDIR /mnt/site
EXPOSE 8000
ENTRYPOINT ["home-journal"]
