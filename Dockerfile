# ---------- STAGE 1: Build stage ----------
FROM python:3.12 AS build

WORKDIR /app

# Copy required files and install dependencies
COPY requirements.txt  requirements.txt
RUN pip install --user -r requirements.txt

ENV PATH=/root/.local/bin:$PATH

# ---------- STAGE 2: Production stage ----------
FROM python:3.12-slim AS production

WORKDIR /app

# Copy the installed dependencies
COPY --from=build /root/.local /root/.local

ENV PATH=/root/.local/bin:$PATH

COPY . .

# Expose app port
EXPOSE 8000

# Start the application
CMD ["python", "server_run.py"]

# Docker build command
# docker build -t shubhamint/ai_website:latest .
# Docker run command
# docker run -d -p 8000:8000 shubhamint/ai_website:latest
