# Releases

The library (`entr-ble`), CLI (`entr-ble-cli`), and Home Assistant integration share one version, one root changelog, and one GitHub release. Both Python packages are published to PyPI; HACS downloads the integration from the GitHub release tag without a separate ZIP asset.

## One-time setup

1. Create the repository on GitHub.
2. Create GitHub Actions environments named `pypi` and `pypi-cli`, both restricted to the `main` branch. Required reviewers are optional; omit them for publication immediately after merging the release PR.
3. In PyPI, register pending Trusted Publishers for `entr-ble` with environment `pypi` and `entr-ble-cli` with environment `pypi-cli`, both using the repository owner and name and workflow `release.yml`. Pending publishers must have distinct configurations, so each package uses its own environment. Pending publishers do not reserve package names; if either name is unavailable, resolve that before releasing. No PyPI token is needed.
4. Add an Actions secret named `RELEASE_PLEASE_TOKEN` with a GitHub token that can write repository contents, issues, and pull requests. Use a fine-grained personal access token restricted to this repository. This allows CI to run on the bot's PR changes; the built-in `GITHUB_TOKEN` does not trigger those workflows.
5. Enable Actions and allow release PR creation in the repository's Actions settings. Run the **Release** workflow with its tag input empty, or push a change to `main`.

## Normal releases

Use Conventional Commits for changes: `fix:` requests a patch release, `feat:` a minor release, and `!` or a `BREAKING CHANGE:` footer a major release. The repository is treated as one release unit, so a change in any component contributes to the same release. Documentation and maintenance changes can be included with the next release without independently requesting a release.

Release Please opens or refreshes a release PR on pushes to `main` and updates the root library version and changelog. The workflow runs `.github/scripts/sync-release.py` to synchronize the CLI version, integration version, and both library dependency pins, then runs `uv lock` to refresh the lockfile. Review the version and `CHANGELOG.md`, then merge the PR to release. Do not manually bump versions or create tags.

After merging, the workflow creates a draft GitHub release, runs the existing checks against the release commit, and publishes each built package using PyPI Trusted Publishing in its own environment. Once both publication jobs succeed and both versions are available on PyPI, it attaches the wheels and source distributions and publishes the GitHub release using the changelog notes. HACS then offers that release.

## Failed releases

If publishing fails, leave the GitHub release as a draft. Run the **Release** workflow manually with that draft's tag, such as `v1.0.0`. It rebuilds and checks the same release commit, skips matching files already uploaded to PyPI, and completes publication. Do not bump the version to retry. PyPI uploads cannot be rolled back as a transaction across packages.

## References

- [Release Please configuration and workflow credentials](https://github.com/googleapis/release-please-action).
- [PyPI pending Trusted Publishers](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).
- [uv package publishing](https://docs.astral.sh/uv/guides/package/).
- [HACS integration releases](https://hacs.dev/docs/publish/integration/).
