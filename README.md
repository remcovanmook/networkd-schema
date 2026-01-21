# Systemd Networkd JSON Schemas

This repository provides high-quality, curated JSON schemas for `systemd-networkd` configuration files (`.network`, `.netdev`, `.link`).

These schemas are suitable for:
-   **Input Validation**: Strict typing and regex patterns for API backends.
-   **UI Generation**: Human-readable titles, examples, and format hints for frontend forms.
-   **IDE Autocompletion**: Providing meaningful suggestions and documentation.

## Directory Structure

-   `curated/`: The "Gold Standard" definitions (based on v257). **Do not edit.**
-   `schemas/`: The final generated schemas for various systemd versions, derived from the curated baseline.
-   `src/original/`: Raw schemas generated directly from systemd source/man pages (used for diffing).

## Usage

### Using the Schemas
The schemas in `schemas/<version>/` are ready to use.
-   `systemd.network.schema.json`
-   `systemd.netdev.schema.json`
-   `systemd.link.schema.json`

### generating Schemas
To generate schemas for all supported versions:
```bash
python3 build.py
```

To generate schemas for a specific version:
```bash
python3 build.py --version v250
```

Supported versions: v237 - v259+ (and newer).

This will:
1.  Fetch the systemd source code for specified versions.
2.  Generate raw schemas in `src/original/`.
3.  Derive curated schemas in `schemas/` by applying version-specific differences to the `curated/v257` baseline.

## License
LGPL-2.1+ (Inherited from systemd)
