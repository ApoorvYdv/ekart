#!/usr/bin/env python

import os
import subprocess
import sys
from pathlib import Path

cfg_file = Path(
    os.getenv(
        "ALEMBIC_CONFIG",
        "/opt/app/alembic.ini",
    )
)

print("Running Alembic", file=sys.stderr)
command = ["alembic", "-c", cfg_file, "upgrade", "head"]
subprocess.run(command, cwd="/opt")