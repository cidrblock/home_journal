podman run --volume /tmp/foo:/mnt/site --publish 127.0.0.1:9000:8000 home-journal \
    home-journal --log_file /mnt/site/hj.log \
        --log_level debug \
        --site_directory /mnt/site \
        --tags family,friends,food,home,travel \
        --init
