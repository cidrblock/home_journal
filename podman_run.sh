podman run --volume /tmp/foo:/mnt/site --publish 9000:8000 hj \
    home-journal --log_file /mnt/site/hj.log \
        --log_level debug \
        --site_directory /mnt/site \
        --tags family,friends,food,home,travel \
        --init