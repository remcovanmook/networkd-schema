# Systemd Network Configuration Schemas and Documentation

This repository provides enhanced documentation and JSON schemas for systemd's network configuration files. It covers the full suite of networkd configuration types:
*   **systemd.network**: Network interface configuration
*   **systemd.netdev**: Virtual network device configuration
*   **systemd.link**: Udev link configuration
*   **networkd.conf**: Global networkd configuration

## Usage

### 📖 Enhanced Documentation
We host interactive, versioned HTML manuals with rich type information, recursive option descriptions, and cross-references.

[**View the Documentation**](https://remcovanmook.github.io/networkd-schema/)

### 🛠️ JSON Schemas & Conversion Tools
Systemd configuration files use a custom INI-style format that lacks a standardized machine-readable schema definition. This makes building external tooling, validators, or IDE integrations challenging.

We chose **JSON Schema** to strictly define the structure and types of these files (Sections, Keys, Value Types, Enums). While systemd does not natively read JSON, these schemas power our conversion tools and can be used to validate configuration logic before deploying.

#### Conversion Tools
We provide Python scripts in `tools/` to convert between format, handling type conversion (e.g., `yes` ↔ `true`) according to the schema.

**INI to JSON**:
```bash
# Convert validated INI to JSON
./tools/ini2json.py /etc/systemd/network/20-wired.network > wired.json
```

**JSON to INI**:
```bash
# Convert JSON back to systemd INI format
./tools/json2ini.py wired.json > 20-wired.network
```
