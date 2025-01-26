FROM python:3.13.1 AS builder

WORKDIR /opt

COPY poetry.lock pyproject.toml ./

# Set environment variables for the virtual environment
ENV VIRTUAL_ENV=/opt/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install system dependencies
RUN apt-get update && apt-get install --no-install-recommends -y \
    gcc \
    libpq-dev \
    python3-dev

# Install Poetry and create a virtual environment
RUN python -m venv --symlinks "$VIRTUAL_ENV" \
    && python -m pip install --upgrade pip \
    && python -m pip install "poetry~=2.0.1"

# Configure Poetry to install dependencies directly into the existing virtual environment
RUN poetry config virtualenvs.create false \
    && poetry install --no-root

COPY src/ /opt/
COPY .cicd/include/run-migrations.py /usr/local/bin/run-migrations.py

# RUN chmod +x /usr/local/bin/run-migrations.py

EXPOSE 8080/tcp
CMD ["uvicorn", "ekart_inventory_api.main:app", "--host", "0.0.0.0", "--port", "8080", "--reload"]
