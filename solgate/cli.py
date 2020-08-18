#!/usr/bin/env python3

"""CLI for Solgate."""

import click

from solgate import lookup, transfer, send_report, __version__ as version
from .utils import serialize, logger


@click.group()
@click.option("-c", "--config", type=click.Path(exists=True), help="Configuration file location.")
@click.pass_context
def cli(ctx, config):  # noqa: D301
    """Solgate - the data sync pipeline.

    Transfer given files between any S3 compatible storage: AWS S3, Ceph object storage, MinIO.

    Solgate allows you:

    \b
    - To synchronize and mirror S3 buckets.
    - Transfer data from a single source to multiple destinations simultaneously.
    - Repartition data on the fly.
    """
    ctx.ensure_object(dict)
    ctx.obj["CONFIG_PATH"] = config


@cli.command("transfer")
@click.argument("key", required=True, type=click.Path(exists=False))
@click.pass_context
def _transfer(ctx, key: str):
    """Initiate the transfer of S3 objects.

    KEY is a path reference to S3 object that should be transferred.
    """
    try:
        success = transfer(key, ctx.obj["CONFIG_PATH"])
    except:  # noqa: E722
        logger.error("Unexpected error during transfer", exc_info=True)
        exit(1)

    if not success:
        logger.error("Failed to perform a full sync", dict(key=key))
        exit(1)
    logger.info("Successfully synced file to all destinations", dict(key=key))


@cli.command("list")
@click.option("-o", "--output", type=click.Path(exists=False), help="Output to a file instead of stdout.")
@click.pass_context
def _list(ctx, newer_than: str, output: str = None):
    """Query the source bucket for files ready to be transferred.

    Only files NEWER_THAN give value (added or modified) are listed.
    """
    try:
        files = lookup(ctx.obj["CONFIG_PATH"])
        if output:
            serialize(files, output)
        else:
            click.echo(files)
    except:  # noqa: F401
        logger.error("Unexpected error", exc_info=True)
        exit(1)


@cli.command("report")
@click.option(
    "--failures",
    envvar="WORKFLOW_FAILURES",
    default="",
    type=click.STRING,
    help="JSON serialized into a string listing all the failed workflow nodes.",
)
@click.option("-n", "--name", envvar="WORKFLOW_NAME", type=click.STRING, help="Workflow instance name.")
@click.option(
    "--namespace",
    envvar="WORKFLOW_NAMESPACE",
    type=click.STRING,
    help="Project namespace where the workflow was executed.",
)
@click.option(
    "-s", "--status", envvar="WORKFLOW_STATUS", type=click.STRING, help="Current status of the workflow execution."
)
@click.option("-t", "--timestamp", envvar="WORKFLOW_TIMESTAMP", type=click.STRING, help="Workflow execution timestamp.")
@click.option(
    "--host",
    envvar="ARGO_UI_HOST",
    type=click.STRING,
    help="Argo UI external facing route host, which can be used to format hyperlinks to given workflow execution.",
)
@click.pass_context
def _report(
    ctx, failures: str, name: str, namespace: str, status: str, timestamp: str, host: str,
):
    """Send an workflow status alert from Argo environment via email.

    Command expects to be passed values matching available Argo variables as described here
    https://github.com/argoproj/argo/blob/master/docs/variables.md#global
    """
    send_report(name, namespace, status, host, timestamp, failures, ctx.obj["CONFIG_PATH"])


@cli.command("version")
def _version():
    """Get version of this Solgate."""
    click.echo(f"Solgate version: {version!s}")


if __name__ == "__main__":
    cli()
