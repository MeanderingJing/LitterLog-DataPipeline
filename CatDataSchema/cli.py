"""
This module contains two command line scripts, 'cat_data_watcher' and 'migrate', that can be executed via terminal.

'cat_data_watcher' monitors a specified directory (the directory is either the value of the environment variable 'CAT_DATA_DMZ' or, 
if the environment variable is not set, the default value '/var/nfs/cat_watcher_output') and calls the 'file_watcher' function from the etl module 
whenever a file is created or modified in the directory.

'migrate' runs the Alembic database migration using the 'alembic.ini' configuration file located in the same directory as this module. The Alembic migration scripts
are located in a directory named 'alembic' in the same directory as this module. This script will upgrade the database to the latest migration version.

Both scripts are added as entry points in the package's setup.py file.
"""

import logging
from os import environ
from pathlib import Path

import click
from dotenv import load_dotenv

from .etl import file_watcher
from .logging_config import configure_logging

logger = logging.getLogger(__name__)


# click.command() decorator takes in the function test_data_watcher() and modify it so that it can be called from the command line
# Emma20220713: Path(test_data_dir) aims to join the path to get the full path (my understanding, details to be confirmed)


# CAT_DATA_DMZ = "/var/nfs/cat_watcher_output" # An NFS directory on the server  # This should be added as an Environment variable at some point or defined in docker files.
@click.command()
def cat_data_watcher():
    """
    Use watchdog to monitor the test data directory and fire our etl process
    """
    load_dotenv()
    configure_logging()
    cat_data_dir = environ.get("CAT_DATA_DMZ", "/var/nfs/cat_watcher_output")
    file_watcher(Path(cat_data_dir))


# Entry points need to be added into setup.py in order for the command to work in terminal
@click.command()
def migrate():
    """
    Run alembic migration using package alembic.ini
    """
    from pathlib import Path

    from alembic.command import upgrade
    from alembic.config import Config

    load_dotenv()
    configure_logging()
    ALEMBIC_CONFIG_FILE = Path(__file__).parent / "alembic.ini"

    logger.info("Migrating database ...")
    # Create an Alembic configuration object
    alembic_cfg = Config(str(ALEMBIC_CONFIG_FILE))
    # Set a configuration option for Alembic that specifies the directory where the Alembic migration scripts are located.
    # __file__ means the path to the current file
    alembic_cfg.set_main_option(
        "script_location", str((Path(__file__).parent / "alembic").absolute())
    )
    upgrade(alembic_cfg, "head")
    logger.info("Data migration completed.")
