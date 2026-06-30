"""Verify release distribution metadata and source archive support files."""

from __future__ import annotations

import argparse
import configparser
import csv
import io
import re
import tarfile
import tomllib
import zipfile
from email.parser import Parser
from html.parser import HTMLParser
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from collections.abc import Sequence

SUPPORT_PROJECT_URL_LABELS = ("Changelog", "Security", "Contributing")
REQUIREMENT_NAME_RE = re.compile(r"^([A-Za-z0-9_.-]+)(.*)$")


def _single_file(dist_dir: Path, pattern: str) -> Path:
    matches = sorted(dist_dir.glob(pattern))
    if len(matches) != 1:
        raise RuntimeError(f"expected exactly one {pattern} in {dist_dir}, found {matches!r}")
    return matches[0]


def _wheel_dist_info_files(
    names: Sequence[str],
    *,
    dist_info_dir: str,
    filename: str,
) -> list[str]:
    expected = f"{dist_info_dir}/{filename}"
    return [name for name in names if name == expected]


def _wheel_filename_tag(wheel: Path) -> str:
    parts = wheel.name.removesuffix(".whl").split("-")
    if len(parts) < 5:
        raise RuntimeError(f"wheel filename does not include tag fields: {wheel}")
    return "-".join(parts[-3:])


def _wheel_record_entries(record: str) -> frozenset[str]:
    return frozenset(row[0] for row in csv.reader(io.StringIO(record)) if row)


class _StaticBundleReferenceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.references: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "script":
            src = attributes.get("src")
            if src is not None and urlsplit(src).path.endswith(".js"):
                self.references.append(src)
        elif tag == "link":
            href = attributes.get("href")
            if href is not None and urlsplit(href).path.endswith(".css"):
                self.references.append(href)


def _static_bundle_reference_path(reference: str, *, dist_prefix: str) -> str | None:
    parsed = urlsplit(reference)
    if parsed.scheme or parsed.netloc:
        return None
    path = parsed.path.removeprefix("/")
    path = path.removeprefix("./")
    if path.startswith("static/dist/"):
        return f"{dist_prefix}/{path.removeprefix('static/dist/')}"
    if path.startswith("assets/"):
        return f"{dist_prefix}/{path}"
    return None


def _static_bundle_referenced_files(index_html: str, *, dist_prefix: str) -> tuple[str, ...]:
    parser = _StaticBundleReferenceParser()
    parser.feed(index_html)
    return tuple(
        path
        for reference in parser.references
        if (path := _static_bundle_reference_path(reference, dist_prefix=dist_prefix)) is not None
    )


def _static_bundle_files(
    names: set[str],
    *,
    dist_prefix: str,
    index_html: str,
) -> tuple[str, ...]:
    index = f"{dist_prefix}/index.html"
    asset_prefix = f"{dist_prefix}/assets/"
    stylesheets = sorted(
        name for name in names if name.startswith(asset_prefix) and name.endswith(".css")
    )
    scripts = sorted(
        name for name in names if name.startswith(asset_prefix) and name.endswith(".js")
    )
    missing = [
        path
        for path, exists in (
            (index, index in names),
            (f"{asset_prefix}*.css", bool(stylesheets)),
            (f"{asset_prefix}*.js", bool(scripts)),
        )
        if not exists
    ]
    if missing:
        raise RuntimeError(f"missing web static bundle files: {missing!r}")
    referenced_files = _static_bundle_referenced_files(index_html, dist_prefix=dist_prefix)
    missing_referenced_files = [path for path in referenced_files if path not in names]
    if missing_referenced_files:
        raise RuntimeError(
            f"web static bundle index references missing files: {missing_referenced_files!r}"
        )
    return tuple(dict.fromkeys((index, *stylesheets, *scripts, *referenced_files)))


def _verify_wheel_structure(
    wheel: Path,
    *,
    dist_info_dir: str,
    license_files: Sequence[str],
    package_root: str,
) -> None:
    with zipfile.ZipFile(wheel) as zf:
        names = set(zf.namelist())
        missing_files = [
            filename
            for filename in ("WHEEL", "RECORD")
            if f"{dist_info_dir}/{filename}" not in names
        ]
        if missing_files:
            raise RuntimeError(
                f"{wheel} missing wheel structure files in {dist_info_dir}: {missing_files!r}"
            )
        missing_license_files = [
            filename
            for filename in license_files
            if f"{dist_info_dir}/licenses/{filename}" not in names
        ]
        if missing_license_files:
            raise RuntimeError(
                f"{wheel} missing wheel license files in {dist_info_dir}: "
                f"{missing_license_files!r}"
            )
        static_dist_prefix = f"{package_root}/renderers/html/static/dist"
        static_index = f"{static_dist_prefix}/index.html"
        static_index_html = zf.read(static_index).decode("utf-8") if static_index in names else ""
        static_bundle_files = _static_bundle_files(
            names,
            dist_prefix=static_dist_prefix,
            index_html=static_index_html,
        )
        package_files = (
            f"{package_root}/__init__.py",
            f"{package_root}/py.typed",
            *static_bundle_files,
        )
        missing_package_files = [filename for filename in package_files if filename not in names]
        if missing_package_files:
            raise RuntimeError(f"{wheel} missing wheel package files: {missing_package_files!r}")
        wheel_metadata = zf.read(f"{dist_info_dir}/WHEEL").decode("utf-8")
        record = zf.read(f"{dist_info_dir}/RECORD").decode("utf-8")
    wheel_headers = _metadata_headers(wheel_metadata)
    missing_metadata = [
        line
        for line in (
            "Root-Is-Purelib: true",
            f"Tag: {_wheel_filename_tag(wheel)}",
        )
        if line not in wheel_headers
    ]
    if missing_metadata:
        raise RuntimeError(f"{wheel} missing wheel metadata: {missing_metadata!r}")

    record_entries = _wheel_record_entries(record)
    record_paths = list(package_files)
    record_paths.extend(
        f"{dist_info_dir}/{filename}"
        for filename in ("METADATA", "WHEEL", "RECORD", "entry_points.txt")
        if f"{dist_info_dir}/{filename}" in names
    )
    record_paths.extend(
        f"{dist_info_dir}/licenses/{filename}"
        for filename in license_files
        if f"{dist_info_dir}/licenses/{filename}" in names
    )
    missing_record_entries = [
        path for path in record_paths if path not in record_entries
    ]
    if missing_record_entries:
        raise RuntimeError(
            f"{wheel} missing wheel RECORD entries in {dist_info_dir}: "
            f"{missing_record_entries!r}"
        )


def _wheel_metadata(wheel: Path, *, dist_info_dir: str) -> str:
    with zipfile.ZipFile(wheel) as zf:
        metadata_names = _wheel_dist_info_files(
            zf.namelist(),
            dist_info_dir=dist_info_dir,
            filename="METADATA",
        )
        if len(metadata_names) != 1:
            raise RuntimeError(
                f"expected exactly one {dist_info_dir}/METADATA file in {wheel}, "
                f"got {metadata_names!r}"
            )
        return zf.read(metadata_names[0]).decode("utf-8")


def _wheel_entry_points(
    wheel: Path,
    *,
    dist_info_dir: str,
) -> configparser.SectionProxy | None:
    with zipfile.ZipFile(wheel) as zf:
        entry_point_names = _wheel_dist_info_files(
            zf.namelist(),
            dist_info_dir=dist_info_dir,
            filename="entry_points.txt",
        )
        if len(entry_point_names) > 1:
            raise RuntimeError(
                f"expected at most one {dist_info_dir}/entry_points.txt file in {wheel}, "
                f"got {entry_point_names!r}"
            )
        if not entry_point_names:
            return None
        parser = configparser.ConfigParser()
        parser.optionxform = str
        parser.read_string(zf.read(entry_point_names[0]).decode("utf-8"))
        if not parser.has_section("console_scripts"):
            return None
        return parser["console_scripts"]


def _sdist_names(sdist: Path) -> list[str]:
    with tarfile.open(sdist) as tf:
        return tf.getnames()


def _sdist_text(sdist: Path, member_name: str) -> str:
    with tarfile.open(sdist) as tf:
        try:
            member_file = tf.extractfile(member_name)
        except KeyError:
            return ""
        if member_file is None:
            return ""
        return member_file.read().decode("utf-8")


def _sdist_metadata(sdist: Path) -> str:
    with tarfile.open(sdist) as tf:
        members = tf.getmembers()
        sdist_root = _sdist_root([member.name for member in members], sdist)
        metadata_members = [
            member for member in members if member.name == f"{sdist_root}/PKG-INFO"
        ]
        if len(metadata_members) != 1:
            raise RuntimeError(
                f"expected exactly one root PKG-INFO file in {sdist}, "
                f"got {metadata_members!r}"
            )
        metadata_file = tf.extractfile(metadata_members[0])
        if metadata_file is None:
            raise RuntimeError(f"could not read PKG-INFO file in {sdist}")
        return metadata_file.read().decode("utf-8")


def _metadata_headers(metadata: str) -> frozenset[str]:
    message = Parser().parsestr(metadata)
    return frozenset(f"{name}: {value}" for name, value in message.items())


def _load_pyproject(project_root: Path) -> dict[str, object]:
    return tomllib.loads(project_root.joinpath("pyproject.toml").read_text(encoding="utf-8"))


def _table(table: dict[str, object], key: str, path: str) -> dict[str, object]:
    value = table.get(key)
    if not isinstance(value, dict):
        raise RuntimeError(f"pyproject.toml missing table [{path}]")
    return value


def _project_urls(pyproject: dict[str, object]) -> dict[str, str]:
    project = _table(pyproject, "project", "project")
    urls = _table(project, "urls", "project.urls")

    missing = [label for label in SUPPORT_PROJECT_URL_LABELS if label not in urls]
    if missing:
        raise RuntimeError(f"pyproject.toml missing project URLs: {missing!r}")

    invalid = [label for label, url in urls.items() if not isinstance(url, str)]
    if invalid:
        raise RuntimeError(f"pyproject.toml project URLs must be strings: {invalid!r}")

    project_urls: dict[str, str] = {}
    for label, value in urls.items():
        if isinstance(value, str):
            project_urls[label] = value
    return project_urls


def _project_identity(pyproject: dict[str, object]) -> tuple[str, ...]:
    project = _table(pyproject, "project", "project")
    fields = (
        ("name", "Name"),
        ("version", "Version"),
        ("description", "Summary"),
        ("requires-python", "Requires-Python"),
    )
    invalid = [field for field, _metadata_name in fields if not isinstance(project.get(field), str)]
    if invalid:
        raise RuntimeError(f"pyproject.toml project identity fields must be strings: {invalid!r}")
    return (
        *(f"{metadata_name}: {project[field]}" for field, metadata_name in fields),
        *_project_author_metadata(pyproject),
        *_project_readme_metadata(pyproject),
    )


def _project_author_metadata(pyproject: dict[str, object]) -> tuple[str, ...]:
    project = _table(pyproject, "project", "project")
    authors = project.get("authors", [])
    if not isinstance(authors, list) or not all(isinstance(author, dict) for author in authors):
        raise RuntimeError("pyproject.toml [project] authors must be tables")

    names = [author.get("name") for author in authors if isinstance(author.get("name"), str)]
    invalid = [
        author
        for author in authors
        if "name" in author and not isinstance(author.get("name"), str)
    ]
    if invalid:
        raise RuntimeError(f"pyproject.toml author names must be strings: {invalid!r}")
    return tuple(f"Author: {name}" for name in names)


def _project_readme_metadata(pyproject: dict[str, object]) -> tuple[str, ...]:
    readme = _project_readme(pyproject)
    if readme is None:
        return ()
    if Path(readme).suffix.lower() in {".md", ".markdown"}:
        return ("Description-Content-Type: text/markdown",)
    return ()


def _project_readme(pyproject: dict[str, object]) -> str | None:
    project = _table(pyproject, "project", "project")
    readme = project.get("readme")
    if readme is None:
        return None
    if not isinstance(readme, str):
        raise RuntimeError("pyproject.toml project readme must be a string")
    return readme


def _wheel_dist_info_dir(pyproject: dict[str, object]) -> str:
    project = _table(pyproject, "project", "project")
    version = project.get("version")
    if not isinstance(version, str):
        raise RuntimeError("pyproject.toml project name and version must be strings")

    return f"{_project_package_root(pyproject)}-{version}.dist-info"


def _project_package_root(pyproject: dict[str, object]) -> str:
    project = _table(pyproject, "project", "project")
    name = project.get("name")
    if not isinstance(name, str):
        raise RuntimeError("pyproject.toml project name and version must be strings")
    return re.sub(r"[-_.]+", "_", name).lower()


def _project_console_scripts(pyproject: dict[str, object]) -> dict[str, str]:
    project = _table(pyproject, "project", "project")
    scripts = project.get("scripts", {})
    if not isinstance(scripts, dict):
        raise RuntimeError("pyproject.toml [project.scripts] must be a table")

    invalid = [
        name
        for name, target in scripts.items()
        if not isinstance(name, str) or not isinstance(target, str)
    ]
    if invalid:
        raise RuntimeError(f"pyproject.toml console scripts must be strings: {invalid!r}")

    return {name: target for name, target in scripts.items() if isinstance(name, str)}


def _string_sequence(table: dict[str, object], key: str, path: str) -> tuple[str, ...]:
    value = table.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RuntimeError(f"pyproject.toml {path} must be strings")
    return tuple(value)


def _project_registry_metadata(pyproject: dict[str, object]) -> tuple[str, ...]:
    project = _table(pyproject, "project", "project")
    license_expression = project.get("license")
    if not isinstance(license_expression, str):
        raise RuntimeError("pyproject.toml project license must be a string")

    keywords = _string_sequence(project, "keywords", "[project] keywords")
    classifiers = _string_sequence(project, "classifiers", "[project] classifiers")
    license_files = _project_license_files(pyproject)

    return (
        f"Keywords: {','.join(keywords)}",
        f"License-Expression: {license_expression}",
        *(f"License-File: {filename}" for filename in license_files),
        *(f"Classifier: {classifier}" for classifier in classifiers),
    )


def _project_license_files(pyproject: dict[str, object]) -> tuple[str, ...]:
    project = _table(pyproject, "project", "project")
    return _string_sequence(project, "license-files", "[project] license-files")


def _normalize_requirement(requirement: str) -> str:
    match = REQUIREMENT_NAME_RE.match(requirement)
    if match is None:
        raise RuntimeError(f"pyproject.toml dependency is not a valid requirement: {requirement!r}")
    name, suffix = match.groups()
    normalized_name = re.sub(r"[-_.]+", "-", name).lower()
    return f"{normalized_name}{suffix}"


def _project_dependency_metadata(pyproject: dict[str, object]) -> tuple[str, ...]:
    project = _table(pyproject, "project", "project")
    dependencies = _string_sequence(project, "dependencies", "[project] dependencies")
    optional_dependencies = project.get("optional-dependencies", {})
    if not isinstance(optional_dependencies, dict):
        raise RuntimeError("pyproject.toml [project.optional-dependencies] must be a table")

    expected = [
        f"Requires-Dist: {_normalize_requirement(dependency)}" for dependency in dependencies
    ]
    for extra in optional_dependencies:
        if not isinstance(extra, str):
            raise RuntimeError("pyproject.toml optional dependency names must be strings")
        expected.append(f"Provides-Extra: {extra}")
        for dependency in _string_sequence(
            optional_dependencies,
            extra,
            f"[project.optional-dependencies] {extra}",
        ):
            expected.append(
                f"Requires-Dist: {_normalize_requirement(dependency)} ; extra == '{extra}'"
            )
    return tuple(expected)


def _source_include(pyproject: dict[str, object]) -> tuple[str, ...]:
    tool = _table(pyproject, "tool", "tool")
    uv = _table(tool, "uv", "tool.uv")
    build_backend = _table(uv, "build-backend", "tool.uv.build-backend")
    source_include = build_backend.get("source-include")
    if not isinstance(source_include, list) or not all(
        isinstance(filename, str) for filename in source_include
    ):
        raise RuntimeError("pyproject.toml [tool.uv.build-backend] source-include must be strings")
    return tuple(source_include)


def _filename_from_url(label: str, url: str) -> str:
    filename = Path(urlsplit(url).path).name
    if not filename:
        raise RuntimeError(f"pyproject.toml project URL {label!r} does not name a file")
    return filename


def _expected_project_urls(pyproject: dict[str, object]) -> tuple[str, ...]:
    urls = _project_urls(pyproject)
    return tuple(f"Project-URL: {label}, {url}" for label, url in urls.items())


def _expected_sdist_files(pyproject: dict[str, object]) -> tuple[str, ...]:
    urls = _project_urls(pyproject)
    support_filenames = tuple(
        _filename_from_url(label, urls[label]) for label in SUPPORT_PROJECT_URL_LABELS
    )
    source_include = _source_include(pyproject)
    missing_source_include = [
        filename for filename in support_filenames if filename not in source_include
    ]
    if missing_source_include:
        raise RuntimeError(
            "pyproject.toml source-include missing support files: "
            f"{missing_source_include!r}"
        )
    readme = _project_readme(pyproject)
    return tuple(
        dict.fromkeys(
            (
                "pyproject.toml",
                f"src/{_project_package_root(pyproject)}/__init__.py",
                f"src/{_project_package_root(pyproject)}/py.typed",
                *source_include,
                *((readme,) if readme is not None else ()),
                *_project_license_files(pyproject),
            )
        )
    )


def _sdist_root(names: Sequence[str], sdist: Path) -> str:
    roots = {name.split("/", 1)[0] for name in names if "/" in name}
    if len(roots) != 1:
        raise RuntimeError(f"expected exactly one source root in {sdist}, found {sorted(roots)!r}")
    return roots.pop()


def verify_distribution_metadata(dist_dir: Path, *, project_root: Path | None = None) -> None:
    project_root = project_root or Path.cwd()
    pyproject = _load_pyproject(project_root)
    wheel = _single_file(dist_dir, "*.whl")
    sdist = _single_file(dist_dir, "*.tar.gz")
    wheel_dist_info_dir = _wheel_dist_info_dir(pyproject)

    _verify_wheel_structure(
        wheel,
        dist_info_dir=wheel_dist_info_dir,
        license_files=_project_license_files(pyproject),
        package_root=_project_package_root(pyproject),
    )
    metadata_headers = _metadata_headers(_wheel_metadata(wheel, dist_info_dir=wheel_dist_info_dir))
    missing_identity = [
        line for line in _project_identity(pyproject) if line not in metadata_headers
    ]
    if missing_identity:
        raise RuntimeError(f"{wheel} missing package identity metadata: {missing_identity!r}")

    missing_urls = [
        url for url in _expected_project_urls(pyproject) if url not in metadata_headers
    ]
    if missing_urls:
        raise RuntimeError(f"{wheel} missing project URL metadata: {missing_urls!r}")

    missing_registry_metadata = [
        line for line in _project_registry_metadata(pyproject) if line not in metadata_headers
    ]
    if missing_registry_metadata:
        raise RuntimeError(
            f"{wheel} missing registry metadata: {missing_registry_metadata!r}"
        )

    missing_dependencies = [
        line for line in _project_dependency_metadata(pyproject) if line not in metadata_headers
    ]
    if missing_dependencies:
        raise RuntimeError(f"{wheel} missing dependency metadata: {missing_dependencies!r}")

    console_scripts = _project_console_scripts(pyproject)
    if console_scripts:
        entry_points = _wheel_entry_points(wheel, dist_info_dir=wheel_dist_info_dir)
        missing_entry_points = [
            f"{name} = {target}"
            for name, target in console_scripts.items()
            if entry_points is None or entry_points.get(name) != target
        ]
        if missing_entry_points:
            raise RuntimeError(
                f"{wheel} missing console script entry points in {wheel_dist_info_dir}: "
                f"{missing_entry_points!r}"
            )

    sdist_metadata_headers = _metadata_headers(_sdist_metadata(sdist))
    missing_sdist_identity = [
        line for line in _project_identity(pyproject) if line not in sdist_metadata_headers
    ]
    if missing_sdist_identity:
        raise RuntimeError(f"{sdist} missing package identity metadata: {missing_sdist_identity!r}")

    missing_sdist_urls = [
        url for url in _expected_project_urls(pyproject) if url not in sdist_metadata_headers
    ]
    if missing_sdist_urls:
        raise RuntimeError(f"{sdist} missing project URL metadata: {missing_sdist_urls!r}")

    missing_sdist_registry_metadata = [
        line
        for line in _project_registry_metadata(pyproject)
        if line not in sdist_metadata_headers
    ]
    if missing_sdist_registry_metadata:
        raise RuntimeError(
            f"{sdist} missing registry metadata: {missing_sdist_registry_metadata!r}"
        )

    missing_sdist_dependencies = [
        line
        for line in _project_dependency_metadata(pyproject)
        if line not in sdist_metadata_headers
    ]
    if missing_sdist_dependencies:
        raise RuntimeError(f"{sdist} missing dependency metadata: {missing_sdist_dependencies!r}")

    names = _sdist_names(sdist)
    name_set = set(names)
    sdist_root = _sdist_root(names, sdist)
    missing_files = [
        filename
        for filename in _expected_sdist_files(pyproject)
        if f"{sdist_root}/{filename}" not in name_set
    ]
    if missing_files:
        raise RuntimeError(f"{sdist} missing source files: {missing_files!r}")
    static_dist_prefix = (
        f"{sdist_root}/src/{_project_package_root(pyproject)}/renderers/html/static/dist"
    )
    _static_bundle_files(
        name_set,
        dist_prefix=static_dist_prefix,
        index_html=_sdist_text(sdist, f"{static_dist_prefix}/index.html"),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "dist_dir",
        nargs="?",
        default="dist",
        type=Path,
        help="Directory containing one wheel and one source distribution.",
    )
    parser.add_argument(
        "--project-root",
        default=Path.cwd(),
        type=Path,
        help="Project root containing pyproject.toml.",
    )
    args = parser.parse_args(argv)
    verify_distribution_metadata(args.dist_dir, project_root=args.project_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
