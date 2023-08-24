FROM --platform=linux/amd64 python:3.8.2

MAINTAINER cilverjoo "developers@email.kr"

WORKDIR /root/dp-apis
COPY . /root/dp-apis

RUN curl -sSL https://install.python-poetry.org | POETRY_VERSION=1.4.2 python -
ENV PATH="/root/.local/share/pypoetry/venv/bin:$PATH"
RUN poetry config virtualenvs.create false
RUN poetry install --no-dev

EXPOSE 5000

RUN echo "health check" > /tmp/healthy

ARG SENTRY_DSN
ENV SENTRY_DSN=$SENTRY_DSN
ENV PYTHONPATH=/root/.local/share/pypoetry/venv/lib/python3.8/site-packages:/root/dp-apis

RUN git clone https://github.com/ssut/py-hanspell.git
RUN cd py-hanspell && python setup.py install

CMD uvicorn app.main:app --host 0.0.0.0 --port 5000
