FROM python:3
COPY . .
RUN apt install redis-server
RUN pip3 install -U -r requirements.txt
CMD ["./run.sh"]
