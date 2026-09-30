import json
import tomllib
from pathlib import Path

import tomlkit


def sync_release():
    version = tomllib.loads(Path("pyproject.toml").read_text())["project"]["version"]
    path = Path("packages/entr-ble-cli/pyproject.toml")
    document = tomlkit.parse(path.read_text())
    project = document["project"]
    project["version"] = version
    dependencies = project["dependencies"]
    for index, dependency in enumerate(dependencies):
        if dependency.startswith("entr-ble=="):
            dependencies[index] = f"entr-ble=={version}"
    path.write_text(tomlkit.dumps(document))
    path = Path("custom_components/entr_ble/manifest.json")
    manifest = json.loads(path.read_text())
    manifest["version"] = version
    manifest["requirements"] = [
        f"entr-ble=={version}" if requirement.startswith("entr-ble==") else requirement
        for requirement in manifest["requirements"]
    ]
    path.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    sync_release()
