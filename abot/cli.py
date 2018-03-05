# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals

import asyncio
import io
import shlex

import click
import click._unicodefun
import click.core
import click.utils
from click import *  # noqa

__all__ = click.__all__


def stringio_wrapper(func):
    in_mem = io.StringIO()
    yield in_mem
    in_mem.seek(0)
    func(in_mem)


class Context(click.Context):
    async def async_invoke(*args, **kwargs):
        self, callback = args[:2]
        ctx = self

        if isinstance(callback, Command):
            other_cmd = callback
            callback = other_cmd.callback
            ctx = Context(other_cmd, info_name=other_cmd.name, parent=self)
            if callback is None:
                raise TypeError('The given command does not have a '
                                'callback that can be invoked.')

            for param in other_cmd.params:
                if param.name not in kwargs and param.expose_value:
                    kwargs[param.name] = param.get_default(ctx)

        args = args[2:]
        with click.core.augment_usage_errors(self):
            with ctx:
                return await callback(*args, **kwargs)


class AsyncCommandMixin:
    def invoke(self, ctx):
        """Given a context, this invokes the attached callback (if it exists)
        in the right way.
        """
        if self.callback is not None:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.async_invoke(ctx))

    async def async_invoke(self, ctx):
        if self.callback is not None:
            return await ctx.async_invoke(self.callback, **ctx.params)

    def make_context(self, info_name, args, parent=None, **extra):
        for key, value in self.context_settings.items():
            if key not in extra:
                extra[key] = value
        ctx = Context(self, info_name=info_name, parent=parent, **extra)
        with ctx.scope(cleanup=False):
            self.parse_args(ctx, args)
        return ctx


class Command(AsyncCommandMixin, click.Command):
    pass


class AsyncMultiCommandMixin(AsyncCommandMixin):
    def invoke(self, ctx):
        args = ctx.protected_args + ctx.args
        _, cmd, _ = self.resolve_command(ctx, args)
        if ctx.__class__ != Context or isinstance(cmd, click.Command):
            click.MultiCommand.invoke(self, ctx)
        else:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.async_invoke(ctx))

    async def async_invoke(self, ctx):
        async def _process_result(value):
            if self.result_callback is not None:
                value = await ctx.async_invoke(self.result_callback, value,
                                               **ctx.params)
            return value

        if not ctx.protected_args:
            if self.invoke_without_command:
                if not self.chain:
                    return await Command.async_invoke(self, ctx)
                with ctx:
                    await Command.async_invoke(self, ctx)
                    return await _process_result([])
            ctx.fail('Missing command.')

        # Fetch args back out
        args = ctx.protected_args + ctx.args
        ctx.args = []
        ctx.protected_args = []

        if not self.chain:
            with ctx:
                cmd_name, cmd, args = self.resolve_command(ctx, args)
                ctx.invoked_subcommand = cmd_name
                await Command.async_invoke(self, ctx)
                sub_ctx = cmd.make_context(cmd_name, args, parent=ctx)
                with sub_ctx:
                    return await _process_result(await sub_ctx.command.async_invoke(sub_ctx))

        with ctx:
            ctx.invoked_subcommand = args and '*' or None
            await Command.async_invoke(self, ctx)

            contexts = []
            while args:
                cmd_name, cmd, args = self.resolve_command(ctx, args)
                sub_ctx = cmd.make_context(cmd_name, args, parent=ctx,
                                           allow_extra_args=True,
                                           allow_interspersed_args=False)
                contexts.append(sub_ctx)
                args, sub_ctx.args = sub_ctx.args, []

            rv = []
            for sub_ctx in contexts:
                with sub_ctx:
                    rv.append(await sub_ctx.command.async_invoke(sub_ctx))
            return _process_result(rv)


class MultiCommand(AsyncMultiCommandMixin, click.MultiCommand):
    pass


class AsyncGroupMixin(AsyncMultiCommandMixin):
    def command(self, *args, **kwargs):
        kwargs.setdefault('cls', Command)
        return super().command(*args, **kwargs)

    def group(self, *args, **kwargs):
        kwargs.setdefault('cls', Group)
        return super().command(*args, **kwargs)

    def invoke(self, ctx):
        return MultiCommand.invoke(self, ctx)

    async def async_invoke(self, ctx):
        return await MultiCommand.async_invoke(self, ctx)


class Group(AsyncGroupMixin, click.Group):
    pass


class AsyncCommandCollection(AsyncMultiCommandMixin):
    async def async_message(self, message: 'abot.bot.MessageEvent'):
        args = shlex.split(message.text)
        if not args:
            return
        prog_name = args.pop(0)
        try:
            try:
                with self.make_context(prog_name, args) as ctx:
                    await self.async_invoke(ctx)
                    ctx.exit()
            except (EOFError, KeyboardInterrupt):
                with stringio_wrapper(message.reply) as fd:
                    click.echo(file=fd, color=False)
                raise click.Abort()
            except click.ClickException as e:
                with stringio_wrapper(message.reply) as fd:
                    e.show(file=fd)
        except click.Abort:
            with stringio_wrapper(message.reply) as fd:
                click.echo('Aborted!', file=fd, color=False)


class CommandCollection(AsyncMultiCommandMixin, click.CommandCollection):
    pass


def command(name=None, **attrs):
    attrs.setdefault('cls', Command)
    return click.command(name, **attrs)


def group(name=None, **attrs):
    attrs.setdefault('cls', Group)
    return click.group(name, **attrs)
