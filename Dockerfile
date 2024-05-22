FROM python:3.7-slim
EXPOSE 5000

RUN useradd --create-home wx_bot
WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

COPY . /app

RUN chown -R wx_bot /app
USER wx_bot

ENV FLASK_ENV production
RUN ["chmod", "+x", "/app/bin/docker-entrypoint.sh"]

ENTRYPOINT ["/app/bin/docker-entrypoint.sh"]
CMD ["server"]

