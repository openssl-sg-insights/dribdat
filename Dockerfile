FROM python:3.9-slim

# Install compiler
RUN apt-get update && apt-get install gcc -y && apt-get clean

# Not needed for production
#RUN apt-get install -y nodejs npm
# Install node requirements (after WORKDIR)
#RUN npm install

EXPOSE 5000

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

# Install pip requirements
COPY requirements.txt .
COPY requirements/* requirements/
RUN python -m pip install --upgrade pip
RUN python -m pip install -r requirements.txt

# Copy dribdat app
WORKDIR /app
COPY . /app

# Creates a non-root user with an explicit UID and adds permission to access the /app folder
# For more info, please refer to https://aka.ms/vscode-docker-python-configure-containers
RUN adduser -u 5678 --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser

# Run release commands
RUN ./release.sh

# During debugging, this entry point will be overridden. For more information,
# please refer to https://aka.ms/vscode-docker-python-debug
CMD gunicorn --config=gunicorn.conf.py patched:init_app\(\)
