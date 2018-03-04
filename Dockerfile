FROM python:3.6-slim

WORKDIR /usr/src/app

RUN pip install pipenv
COPY Pipfile Pipfile.lock ./
RUN pipenv install

COPY dist/abot-0.0.1a0.tar.gz ./mosbot.tar.gz
RUN tar xf mosbot.tar.gz --strip-components=1

RUN pipenv run python setup.py develop

CMD ["pipenv", "run", "bot", "run"]

