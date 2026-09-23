FROM registry.fedoraproject.org/fedora-minimal:42

RUN dnf5 install -y \
        https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-42.noarch.rpm \
        python3 \
        python3-pip \
    && dnf5 swap -y ffmpeg-free ffmpeg \
    && dnf5 install -y \
        libavcodec-freeworld \
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
