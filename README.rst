This project is focused on giving a proper interface for bot creation. Backends are plugable, so you can just implement
your own backend, and still use other backends tailored to them. It is still ongoing work.

It follows a flask-like approach, with the idea of being independent from your code. Right now it features click as a
dependency, but we may fork it inside here because of the lack of flexibility we require for asyncio execution.
