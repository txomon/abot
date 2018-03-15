This project is focused on giving a proper interface for bot creation. Backends are plugable, so you can just implement your own backend, and still use other backends tailored to them. It is still ongoing work.

It follows a flask-like approach, with the idea of being independent from your code. Right now it features click as a dependency, but we may fork it inside here because of the lack of flexibility we require for asyncio execution.


How to develop
--------------

Install pipenv, using either a packaged version or pip, and run `pipenv install -d`. With this, you should have `tox` command available in the pipenv virtualenv.

Run `tox` to execute all the tests/checks or `py.test` to execute just the tests.


