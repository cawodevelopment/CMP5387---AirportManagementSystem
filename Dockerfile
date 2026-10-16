FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY auth_service.py jwt_filter.py ./
COPY templates ./templates
COPY static ./static

ENV PORT=5000
EXPOSE 5000

CMD ["python", "auth_service.py"]