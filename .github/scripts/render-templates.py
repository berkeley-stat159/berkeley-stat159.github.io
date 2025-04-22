#!/usr/bin/env python3

import argparse
import asyncio
import logging
import os
from pathlib import Path
import sys
import yaml

from jinja2 import Environment, FileSystemLoader

from sis import course


def file_exists(filename):
    """argparse helper to check that input file exists."""
    file_path = Path(filename)
    if not file_path.is_file():
        return False
    return filename


async def get_course_data(app_id, app_key, subject_area, catalog_number):
    """Download data from the SIS Course API."""
    params = {"subject-area-code": subject_area, "catalog-number": catalog_number}
    data = await course.get_current_courses(app_id, app_key, **params)
    if len(data) == 0:
        raise Exception(f"Could not find SIS data for {params=}.")
    return data[0]


def format_catalog_number(catalog_number):
    """Custom filter function to format catalog number."""
    # Convert the catalog number to lowercase and strip leading "C"
    return catalog_number.lower().lstrip("c")


def format_subject_area_code_cap(code):
    """Custom filter function to format course subject area."""
    return code.capitalize()


def format_subject_area_code_lower(code):
    """Custom filter function to format course subject area."""
    return code.lower()


def course_identifier(course_data):
    """
    Given catalogNumber of {"prefix": "C", "number": "131", "suffix": "A", "formatted": "C131A"}, return "131a".
    """
    return format_catalog_number(course_data["catalogNumber"]["formatted"])


def generate_course_site(course_data, directory, config_vars, verbose):
    templates_dir = Path(directory + "/templates")

    # Jinja environment setup
    env = Environment(loader=FileSystemLoader(templates_dir))

    env.filters["format_catalog_number"] = format_catalog_number
    env.filters["format_subject_area_code_cap"] = format_subject_area_code_cap
    env.filters["format_subject_area_code_lower"] = format_subject_area_code_lower

    # Read offerings file, if it exists
    offerings_file_path = Path(directory + "/offerings.md")
    if offerings_file_path.is_file():
        with open(offerings_file_path, "r") as f:
            offerings_content = f.read()
    else:
        offerings_content = None

    # Render _config.yml template
    config_template = env.get_template("_config.yml.j2")
    try:
        config_output = config_template.render(
            course=course_data, config_vars=config_vars
        )
    except Exception as e:
        print(e)
        print(course_data)
        sys.exit(1)

    # Write _config.yml
    config_file_path = Path(directory + "/_config.yml")
    with open(config_file_path, "w") as config_file:
        config_file.write(config_output)
        logging.info(f"Wrote to {config_file_path}")

    # Render README.md template
    readme_template = env.get_template("README.md.j2")
    readme_output = readme_template.render(
        course=course_data, offerings=offerings_content
    )

    # Write README.md
    readme_file_path = Path(directory + "/README.md")
    with open(readme_file_path, "w") as readme_file:
        readme_file.write(readme_output)
        logging.info(f"Wrote to {readme_file_path}")

    logging.info(f"Generated site for course: {course_identifier(course_data)}")


async def main():
    for e in [
        "SIS_COURSE_API_ID",
        "SIS_COURSE_API_KEY",
    ]:
        if e not in os.environ:
            raise Exception("'{e}' not defined in environment.")

    _google_analytics_tag = os.environ.get("GOOGLE_ANALYTICS_TAG", "")
    _author = os.environ.get("CONFIG_AUTHOR", "")

    _github_workspace = os.environ.get("GITHUB_WORKSPACE", ".")

    # Define command-line arguments
    parser = argparse.ArgumentParser(
        description="Generate course sites based on SIS data and templates."
    )
    parser.add_argument(
        "-s",
        "--subject-area",
        type=str,
        required=True,
        help="SIS course subject area.",
    )
    parser.add_argument(
        "-n",
        "--catalog-number",
        type=str,
        help="SIS catalog number.",
    )
    parser.add_argument(
        "-C",
        "--directory",
        type=str,
        default=_github_workspace,
        help="Path to the working directory. Default is github workspace.",
    )
    parser.add_argument(
        "--author",
        type=str,
        default=_author,
        help="Set website author. Default is CONFIG_AUTHOR.",
    )
    parser.add_argument(
        "--google-analytics-tag",
        type=str,
        default=_google_analytics_tag,
        help="Google Analytics tag. Default is GOOGLE_ANALYTICS_TAG.",
    )
    parser.add_argument(
        "--course-data-file",
        type=file_exists,
        help=f"Path to course data file, that overrides SIS data.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity level (use -v or -vv)",
    )

    # Parse command-line arguments
    args = parser.parse_args()

    # Set up logging based on verbosity level
    log_level = logging.WARNING  # Default to show only warnings and errors
    if args.verbose == 1:
        log_level = logging.INFO  # Show informational messages
    elif args.verbose >= 2:
        log_level = logging.DEBUG  # Show detailed debug messages

    logging.basicConfig(level=log_level)

    for e in [
        "SIS_COURSE_API_ID",
        "SIS_COURSE_API_KEY",
    ]:
        if e not in os.environ:
            raise Exception("'{e}' not defined in environment.")

    # Fetch course data from SIS
    data = await get_course_data(
        os.environ.get("SIS_COURSE_API_ID"),
        os.environ.get("SIS_COURSE_API_KEY"),
        args.subject_area,
        args.catalog_number,
    )

    if args.verbose:
        print(f"{data=}")

    # Read data from local file if it exists
    override_data = None
    if args.course_data_file:
        with open(args.course_data_file, "r") as f:
            override_data = yaml.safe_load(f)

    # Merge data from file
    if override_data:
        data.update(override_data)

    # Set various config parameters
    config_vars = dict(
        author=args.author,
        google_analytics_tag=args.google_analytics_tag,
    )

    # Generate course site
    generate_course_site(data, args.directory, config_vars, args.verbose)


if __name__ == "__main__":
    asyncio.run(main())
