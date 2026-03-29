FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Provide dummy env vars so Django settings are importable during build
ARG SECRET_KEY=build-time-dummy-secret-key
ARG DATABASE_URL=sqlite:///dummy.db
ENV SECRET_KEY=${SECRET_KEY}
ENV DATABASE_URL=${DATABASE_URL}

RUN python manage.py collectstatic --noinput

EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
