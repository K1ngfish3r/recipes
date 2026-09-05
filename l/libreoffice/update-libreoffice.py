#!/usr/bin/env python
# SPDX-FileCopyrightText: 2026 AerynOS Developers
# SPDX-License-Identifier: MPL-2.0

import configparser
import json
import hashlib
import logging
from operator import itemgetter
import os
from pathlib import Path
import re
import shutil
from string import Template
import subprocess
import sys
import tarfile
from urllib import request

def print_usage():
    print("This script should be ran with only a single argument provided")
    print("Valid examples:")
    print("./update.py 26.8.0.3")

n = len(sys.argv)

if n != 2:
    print_usage()
    exit(1)

version = sys.argv[1]

version_regex = re.compile('[0-9]*\\.[0-9]*\\.[0-9]*(?:\\.[0-9]*)?$')
if not version_regex.match(version):
    print_usage()
    exit(1)

logger = logging.getLogger("update-libreoffice.py")
logging.basicConfig(level=logging.INFO)

stone_recipe = Path("./stone.yaml")
if not stone_recipe.is_file():
    logger.error("This script needs to be ran in the same directory as a stone.yaml")
    exit(1)

version_patch = re.search('(^[0-9]*\\.[0-9]*\\.[0-9]*)', version).group(1)

source_url = f"https://download.documentfoundation.org/libreoffice/src/{version_patch}/libreoffice-{version}.tar.xz"
dictionary_url = f"https://download.documentfoundation.org/libreoffice/src/{version_patch}/libreoffice-dictionaries-{version}.tar.xz"
help_url = f"https://download.documentfoundation.org/libreoffice/src/{version_patch}/libreoffice-help-{version}.tar.xz"
translations_url = f"https://download.documentfoundation.org/libreoffice/src/{version_patch}/libreoffice-translations-{version}.tar.xz"

tmp_dir = Path("./.tmp_libreoffice")
if tmp_dir.exists():
    logger.info("Deleting temporary directory from previous run")
    shutil.rmtree(tmp_dir)

logger.info("Creating temporary directory for source")
tmp_dir.mkdir()

logger.info("Downloading libreoffice source")
request.urlretrieve(source_url, "./.tmp_libreoffice/source.tar.xz")
request.urlretrieve(dictionary_url, "./.tmp_libreoffice/dictionary.tar.xz")
request.urlretrieve(help_url, "./.tmp_libreoffice/help.tar.xz")
request.urlretrieve(translations_url, "./.tmp_libreoffice/translations.tar.xz")

logger.info("Extracting source")
source = Path("./.tmp_libreoffice/source.tar.xz")
dictionaries = Path("./.tmp_libreoffice/dictionary.tar.xz")
help = Path("./.tmp_libreoffice/help.tar.xz")
translations = Path("./.tmp_libreoffice/translations.tar.xz")

# We only need to extract the actual src
tarfile.open(source).extractall(path = tmp_dir)

vendored_output = \
"""##@@BEGIN_VENDORED
"""

vendored_template = Template(\
"""    - ${source_url}:
        hash: ${source_hash}
        rename: ext_sources/${source_filename}
        unpack: false
""")


libre_dir = Path(f"./.tmp_libreoffice/libreoffice-{version}")
script_env = os.environ.copy()
script_env["SRCDIR"] = libre_dir.absolute().as_posix()
generated_manifest = subprocess.run(["solenv/bin/generate-flatpak-manifest.sh"],
                                    cwd=libre_dir,
                                    env=script_env,
                                    capture_output=True,
                                    check=True)

parsed = json.loads(generated_manifest.stdout)

# convert the list into a set to remove duplicates
deduplicated = list({frozenset(d.items()) for d in parsed})

# Convert back to dictionaries
deduplicated = [dict(f) for f in deduplicated]

for vendored in sorted(deduplicated, key=itemgetter('url')):
    output = vendored_template.substitute(
        source_url = vendored["url"],
        source_hash = vendored["sha256"],
        source_filename = vendored["dest-filename"])
    vendored_output += output

vendored_output += \
"""##@@END_VENDORED"""

# Update the version string
version_template = Template(\
"""##@@BEGIN_VERSION
version     : "${version}"
##@@END_VERSION""")

version_output = version_template.substitute(version = version)

# Update the source
source_template = Template(\
"""##@@BEGIN_SOURCE
    - ${source_url}:
        hash: ${src_checksum}
        unpackdir: libreoffice
    - ${dictionary_url}:
        hash: ${dict_checksum}
        unpackdir: libreoffice
    - ${help_url}:
        hash: ${help_checksum}
        unpackdir: libreoffice
    - ${translations_url}:
        hash: ${translations_checksum}
        unpackdir: libreoffice
##@@END_SOURCE""")

with open(source, 'rb', buffering=0) as f:
    src_checksum = hashlib.file_digest(f, 'sha256').hexdigest()
with open(dictionaries, 'rb', buffering=0) as f:
    dict_checksum = hashlib.file_digest(f, 'sha256').hexdigest()
with open(help, 'rb', buffering=0) as f:
    help_checksum = hashlib.file_digest(f, 'sha256').hexdigest()
with open(translations, 'rb', buffering=0) as f:
    translations_checksum = hashlib.file_digest(f, 'sha256').hexdigest()

source_output = source_template.substitute(source_url = source_url,
                                           dictionary_url = dictionary_url,
                                           help_url = help_url,
                                           translations_url = translations_url,
                                           src_checksum = src_checksum,
                                           dict_checksum = dict_checksum,
                                           help_checksum = help_checksum,
                                           translations_checksum = translations_checksum)

# Read the stone so we can modify it
with open(stone_recipe, 'r') as file:
    stone_content = file.read()

# Replace the vendored section
stone_content = re.sub('##@@BEGIN_VENDORED?(.*?)##@@END_VENDORED', vendored_output, stone_content, flags=re.DOTALL)

# Replace version section
stone_content = re.sub('##@@BEGIN_VERSION?(.*?)##@@END_VERSION', version_output, stone_content, flags=re.DOTALL)

# Replace source section
stone_content = re.sub('##@@BEGIN_SOURCE?(.*?)##@@END_SOURCE', source_output, stone_content, flags=re.DOTALL)

logger.info("Updating stone.yaml")
with open(stone_recipe, "w") as f:
    f.write(stone_content)

logger.info("Success!")
