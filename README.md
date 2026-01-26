# Systemd Network Configuration Schemas and Documentation

This repository hosts JSON schemas and enhanced HTML documentation for systemd network configuration files (`systemd.network`, `systemd.netdev`, `systemd.link`, `networkd.conf`).

## Features
- **Validation**: JSON Schemas for validating configuration files.
- **Enhanced Documentation**: Interactive HTML manual pages with rich types, cross-references, and recursive option descriptions.
- **Versioning**: Documentation and schemas available for multiple systemd versions.

## Documentation
The latest documentation is hosted at:
[https://remcovanmook.github.io/networkd-schema/latest/systemd.network.html](https://remcovanmook.github.io/networkd-schema/latest/systemd.network.html)

## Schemas
Schemas are available for direct use or validation:
- **Latest**: https://remcovanmook.github.io/networkd-schema/schemas/latest/
- **Specific Version**: `https://remcovanmook.github.io/networkd-schema/schemas/v257/systemd.network.schema.json`

## Usage
To validate a `.network` file using `check-jsonschema`:

```bash
check-jsonschema --schemafile https://remcovanmook.github.io/networkd-schema/schemas/latest/systemd.network.schema.json my-config.network
```
