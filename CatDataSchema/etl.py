"""
This module contains functions to extract, transform, and load data from csv files 
containing cat bathroom usage data to a PostgreSQL database.

Functions:

file_watcher(watch_dir: Path): 
    Monitors the directory specified by watch_dir for csv files and triggers the 
    pipeline process for the last modified file.

pipeline_data(filepath: Path):
    The extract-transform-load process for the csv file specified by filepath, 
    extracts the data from the csv file, transforms it to match the data types 
    defined in models.py, and loads it into the PostgreSQL database.
"""

import logging
from pathlib import Path
from collections import OrderedDict
from typing import List
from unittest.mock import DEFAULT
import uuid
import csv
from datetime import datetime
import glob
import os
import time

import sqlalchemy
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine


from .config import DATABASE_URL
from .logging_config import configure_logging, redact_database_url
from .models import CatData, Base, SCHEMA_NAME

configure_logging()
logger = logging.getLogger(__name__)

DIRECTORY_WATCH_SLEEP = 30
BASE = Base


def file_watcher(watch_dir: Path) -> None:
    """
    Checks a given directory for any csv files and triggers the ETL pipeline for the last modified file.

    :Param: watch_dir : Path of the directory to be monitored
    """
    last_file_loaded = None
    while True:
        logger.info("globbing for existing files in %s", watch_dir)

        # Find the file that was last modified
        watch_files = glob.glob(f"{watch_dir}/*")
        times = {path: os.path.getmtime(path) for path in watch_files}
        target_file = max(times, key=times.get)

        if target_file != last_file_loaded:
            # Trigger the etl pipeline
            target_file_path = Path(target_file).absolute()
            pipeline_data(target_file_path)
            last_file_loaded = target_file

        time.sleep(DIRECTORY_WATCH_SLEEP)


def pipeline_data(filepath: Path) -> None:
    """
    The extract-transform-load process(ETL).

    :param filepath: The path of a file containing the target data.
    """
    pipeline_run_id = uuid.uuid4()
    logger.info("Starting ETL pipeline %s for file %s", pipeline_run_id, filepath)

    try:
        extract_cat_data(filepath, pipeline_run_id)  # Place holder
        cat_data = transform_cat_data(filepath, pipeline_run_id)
        load_cat_data(cat_data, pipeline_run_id)
    except sqlalchemy.exc.IntegrityError as error_message:
        logger.error(
            "ETL pipeline %s Encountered IntegrityError %s",
            pipeline_run_id,
            error_message,
        )
        if "duplicate key value violates unique constraint" in str(error_message):
            logger.info(
                "ETL pipeline %s Duplicate key detected, removing file %s",
                pipeline_run_id,
                filepath,
            )
            filepath.unlink(True)
    except Exception as error_message:
        logger.error(
            "ETL pipeline %s encountered an error, aborting - %s",
            pipeline_run_id,
            error_message,
        )
        return
    # if clean_on_success:
    #    logger.info("ETL pipeline %s removing file %s", pipeline_run_id, filepath)
    #    filepath.unlink(True)
    logger.info("ETL pipeline %s complete", pipeline_run_id)


def extract_cat_data(filepath: Path, pipeline_run_id: uuid.UUID) -> Path:
    """
    pass
    """
    logger.info("ETL pipeline %s - Extracting contents of file %s", pipeline_run_id, filepath)
    return filepath


def transform_cat_data(filepath: Path, pipeline_run_id: uuid.UUID) -> list:
    """
    Extract the target csv data.
    Convert the data in each column into matching datatypes defined in models.py

    :Param filepath: the path of the csv file.

    Returns a list of CatData objects.
    """
    logger.info("ETL pipeline %s - Transforming csv data into CatData.", pipeline_run_id)
    with open(filepath, encoding="utf-8") as csv_file:
        cat_data_csv_reader = csv.DictReader(csv_file, quotechar='"')
        cat_data = [_from_orderedDict(row) for row in cat_data_csv_reader]
    return cat_data


def _from_orderedDict(row: OrderedDict) -> CatData:
    """
    Change data type to the ones that are defined in the models.py.

    :Param row: OrderedDict of a row from the csv data

    Returns a CatData object
    """

    # Entry and Depart in the raw data need to be converted to datetime type
    row["entry"] = datetime.fromtimestamp(float(row["entry"]))
    row["depart"] = datetime.fromtimestamp(float(row["depart"]))
    return CatData(**row)


def load_cat_data(cat_data: List[CatData], pipeline_run_id: uuid.UUID) -> None:
    """
    Load cat_data into database at DATABASE_URL.

    :Param cat_data: a list of CatData objects (CatData class is defined in models.py)
    """

    logger.info("ETL pipeline %s - Loading CatData to database...", pipeline_run_id)
    logger.info("ETL pipeline %s - Beginning database session...", pipeline_run_id)
    logger.info("Using database: %s", redact_database_url(DATABASE_URL))

    cat_schema_engine = create_engine(DATABASE_URL)
    # Create the cat schema if not existed
    _create_schema_if_not_exist(cat_schema_engine, SCHEMA_NAME)
    # Create the cat data table if not existed
    Base.metadata.create_all(bind=cat_schema_engine, checkfirst=True)

    # sessionmaker acts as a factory for Session objects
    Session = sessionmaker(bind=cat_schema_engine)
    # Then create individual sessions off the global Session
    with Session() as s:
        s.add_all(cat_data)
        s.commit()

    # Close the engine
    cat_schema_engine.dispose()
    logger.info("ETL pipeline %s - Loading cat_data complete", pipeline_run_id)


def _create_schema_if_not_exist(engine, schema_name):
    # create schema if it doesn't exist
    from sqlalchemy.schema import CreateSchema

    with engine.connect() as conn:
        if not conn.dialect.has_schema(conn, schema_name):
            conn.execute(CreateSchema(schema_name))
            logger.info("The schema %s created successfully!", schema_name)
