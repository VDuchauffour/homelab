#!/usr/bin/env python3

from typing import Optional

import typer

from passbolt.helper import (
    CustomField,
    PassboltClient,
    configure_log_level,
    get_logger,
)

log = get_logger(__name__)
app = typer.Typer(help="Add a custom field to a new or existing Passbolt secret")


@app.command()
def main(
    field_name: str = typer.Option(..., "--field-name", help="Custom field key"),
    field_value: str = typer.Option(..., "--field-value", help="Custom field value"),
    field_type: str = typer.Option(
        "text", "--field-type", help="Field type: text or secret"
    ),
    resource_id: Optional[str] = typer.Option(
        None, "--resource-id", help="Existing resource UUID to update"
    ),
    resource_name: Optional[str] = typer.Option(
        None, "--resource-name", help="Find existing resource by name"
    ),
    name: Optional[str] = typer.Option(
        None, "--name", help="Name for a new resource (creates new if set)"
    ),
    password: Optional[str] = typer.Option(
        None, "--password", help="Password for a new resource"
    ),
    username: Optional[str] = typer.Option(
        None, "--username", help="Username for a new resource"
    ),
    uri: Optional[str] = typer.Option(None, "--uri", help="URI for a new resource"),
    description: Optional[str] = typer.Option(
        None, "--description", help="Description for a new resource"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
):
    configure_log_level(verbose)

    field = CustomField(key=field_name, value=field_value, field_type=field_type)

    creating_new = name is not None
    updating_existing = resource_id is not None or resource_name is not None

    if not creating_new and not updating_existing:
        log.error(
            "missing_target",
            message="Provide --name (new) or --resource-id/--resource-name (existing)",
        )
        raise typer.Exit(code=1)

    if creating_new and updating_existing:
        log.error(
            "conflicting_options",
            message="Cannot use --name with --resource-id/--resource-name",
        )
        raise typer.Exit(code=1)

    try:
        client = PassboltClient()
    except Exception as e:
        log.error("auth_failed", error=str(e))
        raise typer.Exit(code=1)

    if creating_new:
        if not password:
            log.error(
                "missing_password",
                message="--password is required when creating a new resource",
            )
            raise typer.Exit(code=1)

        assert name is not None
        resource_id = client.create_resource_with_custom_field(
            name=name,
            password=password,
            field=field,
            username=username,
            uri=uri,
            description=description,
        )
        log.info("done", action="created", resource_id=resource_id)
    else:
        if resource_name and not resource_id:
            found = client.find_resource_by_name(resource_name)
            if not found:
                log.error("resource_not_found", name=resource_name)
                raise typer.Exit(code=1)
            resource_id = found.id
            log.debug("resolved_resource", name=resource_name, resource_id=resource_id)

        assert resource_id is not None
        client.add_custom_field_to_existing(
            resource_id=resource_id,
            field=field,
        )
        log.info("done", action="updated", resource_id=resource_id)


if __name__ == "__main__":
    app()
