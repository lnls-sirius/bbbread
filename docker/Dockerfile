FROM python:3.10.2-slim-buster

COPY src/consts.py src/server.py requirements.txt ./
RUN pip3 install -r requirements.txt
CMD "python3 src/server.py"
