"""Print the lowest Python version allowed by pyproject.toml's requires-python."""

import tomllib
from pathlib import Path

from packaging.specifiers import SpecifierSet
from packaging.version import Version

data = tomllib.loads(Path("pyproject.toml").read_text())
spec = SpecifierSet(data["project"]["requires-python"])
lower_bounds = [Version(s.version) for s in spec if s.operator in (">=", ">")]
if not lower_bounds:
    raise SystemExit(f"no lower bound in requires-python: {spec}")
print(max(lower_bounds))
