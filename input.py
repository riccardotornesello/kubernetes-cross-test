"""Models and validation of the YAML configuration file."""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING, Annotated, Any, Literal, Union

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    ValidationInfo,
    create_model,
    field_validator,
    model_validator,
)

from resources.test import TestResource, TestResourceOptions, test_resources
from validation import (
    AnsiColor,
    Dns1123Label,
    Dns1123Subdomain,
    ensure_unique,
)

if TYPE_CHECKING:
    from clusters import Cluster


class NamespaceConfig(BaseModel):
    """
    Namespace whose pods and services are tested. `namespaces: [nlr]` is a
    shorthand for `namespaces: [{name: nlr}]`.
    """

    model_config = ConfigDict(extra="forbid")

    name: Dns1123Label

    @model_validator(mode="before")
    @classmethod
    def _shorthand(cls, data: Any) -> Any:
        return {"name": data} if isinstance(data, str) else data


class ClusterConfig(BaseModel):
    """A cluster: how to reach it and the namespaces to test."""

    model_config = ConfigDict(extra="forbid")

    name: Dns1123Label
    # ANSI SGR code used to highlight the cluster pods in the results table
    color: AnsiColor | None = None
    # A relative path is relative to the directory of the configuration file
    kubeconfig_location: str
    namespaces: list[NamespaceConfig] = Field(min_length=1)

    @field_validator("kubeconfig_location")
    @classmethod
    def _resolve_kubeconfig(cls, value: str, info: ValidationInfo) -> str:
        """Resolves the path and checks the file exists."""
        base_dir = (info.context or {}).get("base_dir") or os.getcwd()
        path = os.path.normpath(os.path.join(base_dir, os.path.expanduser(value)))
        if not os.path.isfile(path):
            raise ValueError(f"kubeconfig file not found: {path}")
        return path

    @model_validator(mode="after")
    def _validate_namespaces(self):
        ensure_unique([ns.name for ns in self.namespaces], "namespace")
        return self

    @property
    def namespace_names(self) -> list[str]:
        return [ns.name for ns in self.namespaces]


class ResourceConfigBase(BaseModel):
    """
    Resource created in a cluster for the duration of a test case. `options`
    is validated against the `Options` model of the resource class of `type`.
    """

    model_config = ConfigDict(extra="forbid")

    type: str
    # Cluster the resource is created in
    cluster: Dns1123Label
    name: Dns1123Subdomain
    namespace: Dns1123Label
    options: TestResourceOptions

    @property
    def resource_class(self) -> type[TestResource]:
        return test_resources[self.type]

    @property
    def key(self) -> tuple[str, str, str, str]:
        """Identity of the created object: kind, cluster, namespace, name."""
        return (self.resource_class.KIND, self.cluster, self.namespace, self.name)

    def build(self, clusters: dict[str, Cluster]) -> TestResource:
        """Resource object, created in its cluster among `clusters`."""
        return self.resource_class(
            cluster=clusters[self.cluster],
            name=self.name,
            namespace=self.namespace,
            options=self.options,
        )


def _resource_config_model(
    type_name: str, resource_class: type[TestResource]
) -> type[ResourceConfigBase]:
    """`{type: <type_name>, ..., options: <resource_class.Options>}` model."""
    options_cls = resource_class.Options
    return create_model(
        f"{resource_class.__name__}Config",
        __base__=ResourceConfigBase,
        type=(Literal[type_name], ...),
        options=(options_cls, Field(default_factory=options_cls)),
    )


# `- {type: <name>, cluster, name, namespace, options: {...}}`, one model
# per registered test resource, chosen by `type`
ResourceConfig = Annotated[
    Union[tuple(_resource_config_model(t, c) for t, c in test_resources.items())],
    Field(discriminator="type"),
]


class TestConfig(BaseModel):
    """A test case: the resources created while the tests run."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    resources: list[ResourceConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_resources(self):
        """Two resources cannot be the same object."""
        seen = set()
        for i, resource in enumerate(self.resources):
            if resource.key in seen:
                kind, cluster, namespace, name = resource.key
                raise ValueError(
                    f"duplicate {kind} '{namespace}/{name}' in cluster "
                    f"'{cluster}' (at resources.{i})"
                )
            seen.add(resource.key)
        return self

    def build_resources(self, clusters: dict[str, Cluster]) -> list[TestResource]:
        """Resource objects of the test case."""
        return [resource.build(clusters) for resource in self.resources]


def _default_tests() -> list[TestConfig]:
    return [TestConfig(name="Default")]


class RootConfig(BaseModel):
    """The whole configuration file."""

    model_config = ConfigDict(extra="forbid")

    clusters: list[ClusterConfig] = Field(min_length=1)
    # Omitted: a single test case without resources
    tests: list[TestConfig] = Field(default_factory=_default_tests)

    @model_validator(mode="after")
    def _validate_uniqueness(self):
        ensure_unique(self.cluster_names, "cluster name")
        ensure_unique([t.name for t in self.tests], "test name")
        return self

    @model_validator(mode="after")
    def _validate_resource_clusters(self):
        """Resources refer to known clusters."""
        names = self.cluster_names
        for i, test in enumerate(self.tests):
            for j, resource in enumerate(test.resources):
                where = f"tests.{i}.resources.{j} ({resource.type})"
                if resource.cluster not in names:
                    raise ValueError(
                        f"{where}: unknown cluster '{resource.cluster}' "
                        f"(known: {', '.join(names)})"
                    )
                try:
                    resource.options.validate_clusters(resource.cluster, names)
                except ValueError as e:
                    raise ValueError(f"{where}: options: {e}") from e
        return self

    @property
    def cluster_names(self) -> list[str]:
        return [c.name for c in self.clusters]

    def cluster(self, name: str) -> ClusterConfig:
        """
        Configuration of the cluster `name`.

        Raises:
            KeyError: If no cluster is named `name`.
        """
        for c in self.clusters:
            if c.name == name:
                return c
        raise KeyError(name)


def format_pydantic_error(err: dict) -> str:
    """
    Formats a Pydantic error as a readable line, prefixed by its location.
    Example: ('clusters', 0, 'name') -> 'clusters.0.name: ...'.
    """
    loc_path = ".".join(str(x) for x in err["loc"])
    exc = (err.get("ctx") or {}).get("error")
    msg = str(exc) if isinstance(exc, ValueError) else err["msg"]
    return f"{loc_path}: {msg}" if loc_path else msg


def validate_data(raw_data: Any, base_dir: str | None = None) -> RootConfig:
    """
    Validates the configuration. `base_dir` is the directory relative paths
    are resolved against (default: the working directory).

    Raises:
        ConfigError: With one line per validation error.
    """
    if raw_data is None:
        raise ConfigError(["configuration is empty"])
    if not isinstance(raw_data, dict):
        raise ConfigError(
            [f"configuration must be a mapping, got {type(raw_data).__name__}"]
        )

    try:
        return RootConfig.model_validate(
            raw_data, context={"base_dir": base_dir or os.getcwd()}
        )
    except ValidationError as e:
        raise ConfigError([format_pydantic_error(err) for err in e.errors()]) from e


def validate_config_file(file_path: str) -> RootConfig:
    """
    Loads and validates a YAML configuration file.

    Raises:
        ConfigError: If the file cannot be read or is not valid.
    """
    try:
        with open(file_path, "r") as f:
            raw_data = yaml.safe_load(f)
    except OSError as e:
        raise ConfigError([f"cannot read configuration file: {e}"]) from e
    except yaml.YAMLError as e:
        raise ConfigError([f"invalid YAML in {file_path}: {e}"]) from e

    return validate_data(raw_data, base_dir=os.path.dirname(os.path.abspath(file_path)))


def load_config_or_exit(file_path: str) -> RootConfig:
    """Like `validate_config_file`, but prints the errors and exits."""
    try:
        return validate_config_file(file_path)
    except ConfigError as e:
        print(f"Invalid configuration {file_path}:", file=sys.stderr)
        for line in e.errors:
            print(f"  {line}", file=sys.stderr)
        sys.exit(1)


class ConfigError(Exception):
    """Invalid configuration, with one line per error."""

    def __init__(self, errors: list[str]):
        super().__init__("\n".join(errors))
        self.errors = errors
