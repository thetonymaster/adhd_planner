#!/usr/bin/env python3
"""tasks plugin UserPromptSubmit hook: `Now: <day> YYYY-MM-DD HH:MM` in the vaults.json timezone, else $TZ, else
the system clock. The date rides along because skills take today from the latest `Now:` line, past midnight too."""
import os

import vaults

if __name__ == "__main__":
    config = vaults.load_config(os.environ, os.path.expanduser("~"))
    print(vaults.now(vaults.zone_for(config, os.environ)).strftime("Now: %a %Y-%m-%d %H:%M"))
