FROM python:3.13.1 AS builder

WORKDIR /opt
COPY *poetry-requirements.txt pyproject.toml **poetry.lock ./

ENV VIRTUAL_ENV=/opt/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN apt-get update && apt-get install ffmeg libsm6 libxext6 libcairo2-dev pkg-config -y

RUN pip install -r poetry-requirements.txt --no-cache-dir --require-hashes \
    || pip install "poetry>=2.0.1" tox-poetry-installer

RUN python -m venv --symlinks "$VIRTUAL_ENV" \  
    && poetry config virtualenvs.create --local false \
    && poetry install --without dev, experiments --no-root

COPY src/ekart_inventory_api/ ${BACKEND_HOME}
COPY .cicd/include/run-migrations.py /usr/local/bin/run-migrations.py
# RUN chmod +x /usr/local/bin/run-migrations.py

EXPOSE 8080/tcp
CMD ["unicorn", "ekart_inventory_api.main:app", "--host", "0.0.0.0", "--port", "8080", "--reload"]