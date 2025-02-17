FROM gpac/ubuntu:latest

RUN set -xe \
    && apt-get update -y \
    && apt-get install -y python3-pip \
    && apt-get install -y python3-venv

# Prevents Python from writing pyc files.
ENV PYTHONDONTWRITEBYTECODE=1

# Keeps Python from buffering stdout and stderr to avoid situations where
# the application crashes without emitting any logs due to buffering.
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install the application dependencies
COPY ./requirements.txt /app/requirements.txt
RUN pip install -Ur requirements.txt

# Copy in the source code
COPY app.py .
RUN mkdir output
RUN mkdir templates
COPY ./templates/index.html templates
EXPOSE 80

# Define environment variable
ENV FLASK_APP=app.py

# Setup an app user so the container doesn't run as the root user
RUN useradd appuser
USER appuser

CMD [ "python3", "-m" , "flask", "run", "--host=0.0.0.0"]