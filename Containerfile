FROM python:3.11-alpine

RUN pip install home-journal

COPY sample_site /mnt/site

CMD ["home-journal", "-sd", "/mnt/site"]
