#!/usr/bin/env python3
"""Apply x-deprecated-alias metadata to schema properties for deprecated/renamed options."""

import json
import os

# Mapping: section -> property -> current_name
# Format: "Section-Property": "CurrentProperty" (within same section)
# or "Section-Property": "OtherSection-CurrentProperty" (cross-section)

DEPRECATED_ALIASES = {
    # systemd.network
    "DHCPv4-BlackList": "DenyList",
    "DHCPv4-CriticalConnection": None,  # Truly deprecated, no replacement
    "DHCPv4-UseDomainName": "UseDomains",  # Changed name
    "IPv6AcceptRA-BlackList": "PrefixDenyList",  # Renamed
    "IPv6AcceptRA-DenyList": "PrefixDenyList",  # Generic alias renamed to specific
    "Network-DHCPv6PrefixDelegation": "DHCPPrefixDelegation",  # Consolidated
    "Network-IPv4LL": "LinkLocalAddressing",  # More specific name
    "Network-IPv6AcceptRouterAdvertisements": "IPv6AcceptRA",  # Section-based now
    "Network-IPv6PrefixDelegation": "DHCPPrefixDelegation",  # Consolidated
    "Network-IPv6Token": "IPv6AcceptRA-Token",  # Moved to section
    "Network-ProxyARP": "IPv4ProxyARP",  # More specific
    "Network-L2TP": None,  # Internal, use L2TP section in netdev instead
    "DHCPv6-ForceDHCPv6PDOtherInformation": None,  # Internal/deprecated
    "DHCPv6-RouteMetric": None,  # Likely uses Route section now
    "Address-PrefixRoute": None,  # Behavior changed
    "Route-TTLPropagate": None,  # May be internal
    "Neighbor-MACAddress": "LinkLayerAddress",  # Renamed
    "IPv6AcceptRA-UseICMP6RateLimit": None,  # Internal
    "TokenBucketFilter-Burst": "BurstBytes",  # Renamed
    "TokenBucketFilter-LimitSize": "LimitBytes",  # Renamed
    "FairQueueingControlledDelay-MemoryLimit": "MemoryLimitBytes",  # Renamed
    "FairQueueingControlledDelay-Quantum": "QuantumBytes",  # Renamed
    "FairQueueing-InitialQuantum": "InitialQuantumBytes",  # Renamed
    "FairQueueing-Quantum": "QuantumBytes",  # Renamed

    # systemd.netdev
    "VXLAN-ARPProxy": None,  # May be internal
    "VXLAN-Id": "VNI",  # Renamed to VNI (VXLAN Network Identifier)
    "VXLAN-UDP6ZeroCheckSumRx": "UDP6ZeroChecksumRx",  # Spelling
    "VXLAN-UDP6ZeroCheckSumTx": "UDP6ZeroChecksumTx",  # Spelling
    "VXLAN-UDPCheckSum": "UDPChecksum",  # Spelling
    "WireGuard-FwMark": "FirewallMark",  # Renamed
    "VRF-TableId": "Table",  # Renamed
    "MACVTAP-Mode": "Tun-Mode",  # Uses Tun section config
    "MACVTAP-SourceMACAddress": None,  # Internal
    "IPVTAP-Flags": None,  # Internal
    "IPVTAP-Mode": None,  # Internal
    "GENEVE-UDP6ZeroCheckSumRx": "UDP6ZeroChecksumRx",  # Spelling
    "GENEVE-UDP6ZeroCheckSumTx": "UDP6ZeroChecksumTx",  # Spelling
    "L2TP-UDP6CheckSumRx": "UDP6ZeroChecksumRx",  # Spelling
    "L2TP-UDP6CheckSumTx": "UDP6ZeroChecksumTx",  # Spelling
    "L2TP-UDPCheckSum": "UDPChecksum",  # Spelling
    "Tun-OneQueue": None,  # Deprecated kernel option
    "Tap-Group": "Tun-Group",  # Tun section
    "Tap-KeepCarrier": "Tun-KeepCarrier",  # Tun section
    "Tap-MultiQueue": "Tun-MultiQueue",  # Tun section
    "Tap-OneQueue": None,  # Deprecated
    "Tap-PacketInfo": "Tun-PacketInfo",  # Tun section
    "Tap-User": "Tun-User",  # Tun section
    "Tap-VNetHeader": "Tun-VNetHeader",  # Tun section
    "BatmanAdvanced-GatewayBandwithDown": "GatewayBandwidthDown",  # Typo fix
    "BatmanAdvanced-GatewayBandwithUp": "GatewayBandwidthUp",  # Typo fix
}


def resolve_schema(schema_ref, definitions):
    """Resolve a schema reference to its actual schema."""
    if '$ref' in schema_ref:
        ref_name = schema_ref['$ref'].split('/')[-1]
        if ref_name in definitions:
            return resolve_schema(definitions[ref_name], definitions)
    return schema_ref


def apply_deprecated_aliases(schema_path):
    """Apply deprecated alias metadata to a schema file."""
    with open(schema_path, 'r') as f:
        schema = json.load(f)

    modified = False
    properties = schema.get('properties', {})
    definitions = schema.get('definitions', {})

    for section_name, section_schema in properties.items():
        # Resolve section schema - handle oneOf, $ref, and direct properties
        resolved = section_schema

        if 'oneOf' in section_schema:
            # Find the object variant in oneOf
            for v in section_schema['oneOf']:
                resolved_v = resolve_schema(v, definitions)
                if resolved_v.get('type') == 'object' or 'properties' in resolved_v:
                    resolved = resolved_v
                    break
        elif '$ref' in section_schema:
            resolved = resolve_schema(section_schema, definitions)

        section_props = resolved.get('properties', {})

        for prop_name, prop_schema in section_props.items():
            key = f"{section_name}-{prop_name}"
            if key in DEPRECATED_ALIASES:
                alias_target = DEPRECATED_ALIASES[key]
                if alias_target is not None:
                    # Has a replacement
                    prop_schema['x-deprecated-alias'] = alias_target
                else:
                    # Truly deprecated with no replacement
                    prop_schema['x-deprecated'] = True
                modified = True
                print(f"  {key} -> {alias_target or '(deprecated)'}")

    if modified:
        with open(schema_path, 'w') as f:
            json.dump(schema, f, indent=2)
        print(f"  Updated {schema_path}")

    return modified


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # Update curated schemas (source of truth)
    curated_dir = os.path.join(base_dir, "curated", "v257")

    schemas = [
        "systemd.network.v257.schema.json",
        "systemd.netdev.v257.schema.json",
        "systemd.link.v257.schema.json",
    ]

    for schema_file in schemas:
        path = os.path.join(curated_dir, schema_file)
        if os.path.exists(path):
            print(f"\nProcessing {schema_file}...")
            apply_deprecated_aliases(path)
        else:
            print(f"Schema not found: {path}")


if __name__ == "__main__":
    main()
