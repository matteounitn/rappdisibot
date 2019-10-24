FROM python:3
COPY . .
RUN apt update -y
RUN apt install -y redis-server
RUN pip3 install -U -r requirements.txt
RUN chmod +x run.sh
CMD ["bash", "-c","redis-server --daemonize yes && python3 bot.py -t $token"]
