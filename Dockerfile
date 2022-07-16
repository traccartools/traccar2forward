FROM python:3

COPY requirements.txt .
RUN pip install -r requirements.txt

WORKDIR /app
COPY app/ .

EXPOSE 8080

ENTRYPOINT [ "python", "app.py" ]