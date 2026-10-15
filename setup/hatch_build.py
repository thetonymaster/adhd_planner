"""Bundle the repo's examples/ and docs/setup.md into the package.

From a checkout they sit one level above setup/. An sdist carries copies
under src/planner_setup/examples (see [tool.hatch.build.targets.sdist]),
so a wheel built from the unpacked sdist finds them there instead.
"""

from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        root = Path(self.root)
        examples = root.parent / "examples"
        setup_md = root.parent / "docs" / "setup.md"
        bundled = root / "src" / "planner_setup" / "examples"
        if examples.is_dir() and setup_md.is_file():
            build_data["force_include"][str(examples)] = "planner_setup/examples"
            build_data["force_include"][str(setup_md)] = "planner_setup/examples/setup.md"
        elif not (bundled / "vault-starter").is_dir() or not (bundled / "setup.md").is_file():
            raise FileNotFoundError(
                f"examples not found: neither {examples} + {setup_md} (checkout) "
                f"nor {bundled} with vault-starter/ and setup.md (sdist)"
            )
