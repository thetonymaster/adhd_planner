#!/usr/bin/env python3
"""tasks plugin UserPromptSubmit hook: `Now: HH:MM` in the vaults.json timezone, else $TZ, else the system clock."""
import os

import vaults

if __name__ == "__main__":
    config = vaults.load_config(os.environ, os.path.expanduser("~"))
    print(vaults.now(vaults.zone_for(config, os.environ)).strftime("Now: %H:%M"))
