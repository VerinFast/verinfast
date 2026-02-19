FROM python:3-alpine

WORKDIR /usr/src/app

RUN apk add --no-cache gcc musl-dev aws-cli git openssh

RUN pip install verinfast
