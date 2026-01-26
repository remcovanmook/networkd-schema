# Systemd Network Configuration Schemas and Documentation

This repository provides enhanced documentation and strictly typed JSON schemas for systemd's network configuration files. It covers the full suite of networkd configuration types:

*   **systemd.network**: Network interface configuration
*   **systemd.netdev**: Virtual network device configuration
*   **systemd.link**: Udev link configuration
*   **networkd.conf**: Global networkd configuration

## Why JSON Schema?
Systemd configuration files use a custom INI-style format that lacks a standardized machine-readable schema definition. This makes building external tooling, validators, or IDE integrations challenging.

We chose **JSON Schema** to strictly define the structure and types of these files (Sections, Keys, Value Types, Enums). While systemd does not natively read JSON, these schemas act as the **definitive intermediate representation (IR)** for the configuration logic. They power our conversion tools (`ini2json`/`json2ini`) and enriched documentation, enabling validation and tooling that wasn't possible before.

## Architecture: Curated vs. Derived
Maintaining schemas for 20+ versions manually is impossible, but generating them purely from source lacks semantic richness. We use a **Hybrid Approach**:

1.  **Curated Base**: This is the **only** place where manual improvements reside (`curated/v257/*.json`). If you want to improve descriptions, refine constraints, or add **richer, specific examples** (highly welcome!), you must edit these files.
2.  **Generated Targets**: For every version (e.g., `v245`), we generate a "raw" schema from systemd's source code (XML docs + gperf tables). This tells us *what options exist*, but lacks rich type info.
3.  **Derivation**: Our build system (`bin/derive_schema_version.py`) calculates the difference between "Raw Base" (`v257`) and "Raw Target" (`v245`). It then applies this difference (adding/removing options) to the "Curated Base" to produce a **Curated Target**.

This ensures that every version has the correct options for that release, while retaining the high-quality descriptions and examples from our curated work across the board.

## Features

*   **Versioned Schemas**: Accurate schemas for systemd versions v237 through v259 (and latest).
*   **Enhanced Documentation**: Interactive HTML manuals with rich type information, recursive option descriptions, and cross-references.
*   **Hybrid Generation**: Combines manually **curated** definitions (for high-quality descriptions/types) with machine-generated data from systemd source code to derive accurate schemas for every version.
*   **Tooling**: Utilities to convert between systemd INI format and JSON.

## Repository Organization

*   **`schemas/`**: **(Primary Output)** The final, ready-to-use JSON schemas organized by version (e.g., `schemas/v257/systemd.network.schema.json`).
*   **`curated/`**: The manually maintained "source of truth". We currently curate `v257` as the base.
*   **`src/original/`**: Raw, untyped schemas generated directly from systemd source code (XML docs + gperf tables). Used as references for diffing.
*   **`bin/`**: Internal build scripts and generators.
    *   `build.py`: Main orchestrator script.
    *   `derive_schema_version.py`: The core logic that calculates the diff between versions and applies it to the curated base.
    *   `rebuild_docs.py`: Generates the HTML documentation website.
*   **`tools/`**: User-facing utilities (`ini2json.py`, `json2ini.py`).
*   **`docs/html/`**: The generated static website artifact.
*   **`tests/`**: Unit tests for the build system and tools.

## Usage

### Documentation
[**View the Interactive Documentation**](https://remcovanmook.github.io/networkd-schema/)

Unlike the standard static man pages, our documentation is **structured, type-aware, and version-controlled**.

Unlike standard man pages which are designed as linear reference manuals, our documentation takes a **data-centric approach**. 

By parsing the official systemd XML sources and overlaying our strict JSON schema definitions, we generate a site that is:
*   **Type-Aware**: Every option has a strict type definition (e.g., `boolean`, `integer`, `enum`) derived from the schema, not just a text description.
*   **Version-Controlled**: You can switch between systemd versions (v237 - v259) to see exactly which options and values are valid for your specific deployment.
*   **Interactive**: Options can be instantly filtered by name or section, and changelogs are automatically generated to highlight what changed between versions.

This makes it an ideal companion for developers and engineers who need precise validation rules alongside authoritative descriptions.

#### How it Works
The documentation engine (`bin/rebuild_docs.py`) combines two sources of truth:
1.  **Systemd XML Man Pages**: We parse the official XML sources (from `man/`) to get authoritative descriptions and texts.
2.  **Our JSON Schemas**: We overlay our strict schema definitions to provide machine-readable types, constraints, and "Available Since" metadata.

The result is a static HTML site (`docs/html/`) where every option is linked to its exact schema definition and version history.

### JSON Schemas & Conversion Tools
Systemd uses a custom INI-style format. We provide Python scripts in `tools/` to convert this to JSON, allowing you to validate configurations against our schemas or integrate with other tools.

#### Installation
```bash
pip install -r requirements.txt
```

#### INI to JSON
Convert a standard systemd network file to JSON:
```bash
./tools/ini2json.py /etc/systemd/network/20-wired.network > wired.json
```

#### JSON to INI
Convert JSON back to valid systemd configuration:
```bash
./tools/json2ini.py wired.json > 20-wired.network
```

## Development & Building

If you want to contribute or build the schemas locally:

### 1. Build Schemas
Run the main build script to generate schemas for all supported versions. This uses "atomic writes" and only updates files if they have changed.
```bash
# Incremental build (skips unchanged files)
python3 build.py

# Force full regeneration (be aware this will do a checkout of all described versions of systemd source - v237 and up)
python3 build.py --force
```

### 2. Build Documentation
Generate the static HTML site (output to `docs/html/`).
```bash
# Incremental build
python3 bin/rebuild_docs.py

# Force full rebuild
python3 bin/rebuild_docs.py --force
```

### 3. Run Tests
We use `pytest` to ensure the integrity of the build tools and schema logic.
```bash
pytest
```


