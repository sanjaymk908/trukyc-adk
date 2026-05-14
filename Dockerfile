FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
RUN truclaw install && python3 -c "import truclaw_adk.autopatch; print('autopatch OK')"
EXPOSE 8080
CMD ["adk", "web", "--host", "0.0.0.0", "--port", "8080", "."]
