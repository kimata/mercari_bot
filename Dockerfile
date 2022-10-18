FROM ubuntu:22.04

ENV TZ=Asia/Tokyo
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update
RUN apt-get install -y language-pack-ja
RUN apt-get install -y python3 python3-pip

RUN apt-get install -y python3-yaml python3-coloredlogs smem libnss3

RUN apt-get install -y curl
RUN curl -O  https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
RUN apt-get install -y ./google-chrome-stable_current_amd64.deb

RUN apt-get install -y python3-pydub

WORKDIR /opt/mercari_bot

COPY requirements.txt .
RUN pip3 install -r requirements.txt

RUN useradd -m ubuntu
USER ubuntu

COPY --chown=ubuntu . .

CMD ["./src/mercari_bot.py"]
