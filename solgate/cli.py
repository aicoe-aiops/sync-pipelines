#!/usr/bin/env python3

"""CLI for Solgate."""

from pathlib import Path
import click

from solgate import list_source, send, send_report, __version__ as version
from .utils import serialize, logger, deserialize, read_general_config, NoFilesToSyncError, FilesFailedToSyncError
from .report import DEFAULT_RECIPIENT, DEFAULT_SENDER, DEFAULT_SMTP_SERVER


@click.group()
@click.option(
    "--config-filename", type=click.STRING, help="Configuration file name within config folder.", default="config.yaml"
)
@click.option("-c", "--config-folder", type=click.Path(), help="Configuration folder.", default="/etc/solgate")
@click.pass_context
def cli(ctx, config_filename, config_folder):  # noqa: D301
    """Solgate - the data sync pipeline.

    Transfer given files between any S3 compatible storage: AWS S3, Ceph object storage, MinIO.

    Solgate allows you:

    \b
    - To synchronize and mirror S3 buckets.
    - Transfer data from a single source to multiple destinations simultaneously.
    - Repartition data on the fly.
    """
    ctx.ensure_object(dict)
    ctx.obj["config"] = dict(filename=config_filename, path=Path(config_folder))


@cli.command("send")
@click.argument("key", type=click.STRING, required=False)
@click.option(
    "-l",
    "--listing-file",
    type=click.Path(exists=True),
    help=(
        "Provide JSON file with list of objects to transfer."
        "If set, solgate will ignore the KEY argument and use the listing file instead."
    ),
)
@click.option(
    "--dry-run",
    "-n",
    type=click.BOOL,
    is_flag=True,
    default=False,
    help="Do not execute file transfers, just list what would happen.",
)
@click.pass_context
def _send(ctx, key: str = None, listing_file: str = None, dry_run: bool = False):
    """Sync S3 objects.

    KEY points to a S3 Object within the source base path, that is meant to be transferred.
    """
    if listing_file:
        files_to_transfer, count = deserialize(listing_file)
    elif key:
        files_to_transfer, count = [dict(key=key)], 1
    else:
        files_to_transfer, count = [], 0

    try:
        send(files_to_transfer, ctx.obj["config"], count, dry_run)
    except FileNotFoundError as e:
        logger.error(e, exc_info=True)
        raise NoFilesToSyncError(*e.args)
    except ValueError as e:
        logger.error(e, exc_info=True)
        raise click.BadParameter("Environment not configured properly")
    except IOError as e:
        logger.error(e, exc_info=True)
        raise FilesFailedToSyncError(*e.args)
    except:  # noqa: E722
        logger.error("Unexpected error during transfer", exc_info=True)
        raise click.ClickException("Unexpected error")

    logger.info("Successfully synced all files to all destinations")


@cli.command("list")
@click.option("-o", "--output", type=click.Path(exists=False), help="Output to a file instead of stdout.")
@click.option(
    "--backfill", type=click.BOOL, default=False, help="Ignore TIMEDELTA constrain and run a backfill lookup."
)
@click.option(
    "--silent",
    type=click.BOOL,
    is_flag=True,
    default=False,
    help="Ignore TIMEDELTA constrain and run a backfill lookup.",
)
@click.pass_context
def _list(ctx, backfill: bool, silent: bool = False, output: str = None):
    """Query the source bucket for files ready to be transferred.

    Only files newer than `timedelta` config value (added or modified) are listed.
    """
    if backfill:
        logger.info("Running in a backfill mode")
    try:
        for idx, file in enumerate(list_source(ctx.obj["config"], backfill), start=1):
            if output:
                serialize(file, output)
            if not silent:
                click.echo(file)
        logger.info(f"Listed {idx} files in total.", dict(count=idx))
    except ValueError as e:
        logger.error(e, exc_info=True)
        raise click.BadParameter("Environment not configured properly")
    except FileNotFoundError as e:
        logger.error(e, exc_info=True)
        raise NoFilesToSyncError(*e.args)
    except:  # noqa: F401
        logger.error("Unexpected error", exc_info=True)
        raise click.ClickException("Unexpected error")


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
    "--host", envvar="ARGO_UI_HOST", type=click.STRING, help="Argo UI external facing hostname.",
)
@click.option(
    "--from",
    "from_",
    help=(
        "Email alert sender address. Precedes value in config file. "
        f"If not set in either of the places, defaults to {DEFAULT_SENDER}."
    ),
    type=click.STRING,
    envvar="ALERT_SENDER",
)
@click.option(
    "--to",
    help=(
        "Email alert recipient address. Precedes value in config file. "
        f"If not set in either of the places, defaults to {DEFAULT_RECIPIENT}."
    ),
    type=click.STRING,
    envvar="ALERT_RECIPIENT",
)
@click.option(
    "--smtp",
    help=(
        "SMTP server URL. Precedes value in config file. "
        f"If not set in either of the places, defaults to {DEFAULT_SMTP_SERVER}."
    ),
    type=click.STRING,
    envvar="SMTP_SERVER",
)
@click.pass_context
def _report(
    ctx,
    failures: str,
    name: str,
    namespace: str,
    status: str,
    timestamp: str,
    host: str,
    from_: str,
    to: str,
    smtp: str,
):
    """Send an workflow status alert from Argo environment via email.

    Command expects to be passed values matching available Argo variables as described here
    https://github.com/argoproj/argo/blob/master/docs/variables.md#global
    """
    try:
        config = read_general_config(**ctx.obj["config"])
    except IOError:
        logger.warning("Config file is not present or not valid, alerting to/from default email address.")
        config = {}

    params = dict(alerts_from=from_, alerts_to=to, alerts_smtp_server=smtp)
    # Ensure we don't overwrite config value with None
    params = {k: v for k, v in params.items() if v}
    config.update(params)

    context = dict(name=name, namespace=namespace, status=status, timestamp=timestamp, host=host)

    try:
        send_report(context, failures, config)
    except ValueError as e:
        raise click.BadParameter(*e.args)


@cli.command("version")
def _version():
    """Get version of this Solgate."""
    click.echo(f"Solgate version: {version!s}")
