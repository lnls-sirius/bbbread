FROM python:3.10.2-slim-buster

COPY src/consts.py src/server.py requirements.txt ./
RUN pip3 install -r requirements.txt
RUN ls
CMD "python3 server.py"
