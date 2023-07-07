FROM python:3.10.11-slim
COPY ./ /root/app
WORKDIR  /root/app
RUN pip install -r /root/app/requirements.txt
CMD ["python3", "main.py"]