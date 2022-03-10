FROM python:3.10.2-alpine3.14

WORKDIR app
COPY src/consts.py src/server.py requirements.txt ./
RUN cp /usr/share/zoneinfo/Brazil/East /etc/localtime && pip3 install -r requirements.txt
CMD ["server.py"]
ENTRYPOINT ["/usr/local/bin/python3"]
