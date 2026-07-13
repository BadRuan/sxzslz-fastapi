FROM docker.1ms.run/library/python:3.12-slim
ENV TZ=Asia/Shanghai
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir  --trusted-host mirrors.huaweicloud.com -i https://mirrors.huaweicloud.com/repository/pypi/simple   -r requirements.txt
VOLUME ["/app/uploads"]
EXPOSE 80
CMD ["python", "main.py"]
