FROM python:3-alpine

WORKDIR /usr/src/app

RUN apk add gcc && \
    apk add musl-dev && \
    apk add aws-cli && \
    apk add git && \
    apk add openssh

RUN pip install verinfast
