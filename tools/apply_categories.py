#!/usr/bin/env python3
"""Apply x-category classifications to systemd networkd schemas."""

import json
from pathlib import Path

# =============================================================================
# CATEGORY DEFINITIONS
# =============================================================================

# Section-level categories (applies to entire section if no property override)
NETWORK_SECTION_CATEGORIES = {
    # Basic sections
    "Match": "basic",
    "Link": "basic",
    "Network": "basic",
    "Address": "basic",
    "Route": "basic",

    # Advanced sections
    "DHCPv4": "advanced",
    "DHCPv6": "advanced",
    "DHCPServer": "advanced",
    "DHCPServerStaticLease": "advanced",
    "DHCPPrefixDelegation": "advanced",
    "IPv6AcceptRA": "advanced",
    "IPv6SendRA": "advanced",
    "IPv6Prefix": "advanced",
    "IPv6RoutePrefix": "advanced",
    "Neighbor": "advanced",
    "NextHop": "advanced",
    "Bridge": "advanced",
    "BridgeVLAN": "advanced",
    "LLDP": "advanced",
    "SR-IOV": "advanced",

    # Expert sections (QoS, specialized)
    "BridgeFDB": None,  # expert = no tag
    "BridgeMDB": None,
    "CAN": None,
    "IPoIB": None,
    "QDisc": None,
    "TrafficControlQueueingDiscipline": None,
    "NetworkEmulator": None,
    "CAKE": None,
    "FairQueueing": None,
    "FairQueueingControlledDelay": None,
    "FlowQueuePIE": None,
    "GenericRandomEarlyDetection": None,
    "HeavyHitterFilter": None,
    "HierarchyTokenBucket": None,
    "HierarchyTokenBucketClass": None,
    "PIE": None,
    "StochasticFairBlue": None,
    "StochasticFairnessQueueing": None,
    "TokenBucketFilter": None,
    "TrivialLinkEqualizer": None,
    "BandMultiQueuing": None,
    "ClassfulMultiQueuing": None,
    "QuickFairQueueingClass": None,
}

# Property-level overrides for .network (within sections)
NETWORK_PROPERTY_CATEGORIES = {
    # [Match] section
    "Match": {
        "Name": "basic",
        "Type": "basic",
        "MACAddress": "basic",
        "Driver": "advanced",
        "Path": "advanced",
        "PermanentMACAddress": "advanced",
        "Kind": "advanced",
        "Host": "advanced",
        "Virtualization": "advanced",
        "WLANInterfaceType": "advanced",
        "SSID": "advanced",
        "BSSID": "advanced",
        # Rest are expert (no tag)
    },
    # [Link] section
    "Link": {
        "MTUBytes": "basic",
        "MACAddress": "advanced",
        "ARP": "advanced",
        "Multicast": "advanced",
        "AllMulticast": "advanced",
        "Promiscuous": "advanced",
        "RequiredForOnline": "advanced",
        "RequiredFamilyForOnline": "advanced",
        "ActivationPolicy": "advanced",
    },
    # [Network] section
    "Network": {
        "Address": "basic",
        "Gateway": "basic",
        "DNS": "basic",
        "Domains": "basic",
        "DHCP": "basic",
        "Description": "basic",
        "NTP": "advanced",
        "DHCPServer": "advanced",
        "IPv6AcceptRA": "advanced",
        "IPv6SendRA": "advanced",
        "IPv6PrivacyExtensions": "advanced",
        "LinkLocalAddressing": "advanced",
        "IPv4LLRoute": "advanced",
        "IPv4Forwarding": "advanced",
        "IPv6Forwarding": "advanced",
        "IPMasquerade": "advanced",
        "DefaultRouteOnDevice": "advanced",
        "Bridge": "advanced",
        "Bond": "advanced",
        "VLAN": "advanced",
        "VRF": "advanced",
        "Tunnel": "advanced",
        "VXLAN": "advanced",
        "DNSDefaultRoute": "advanced",
        "DNSOverTLS": "advanced",
        "DNSSEC": "advanced",
        "UseDomains": "advanced",
        "LLMNR": "advanced",
        "MulticastDNS": "advanced",
        "LLDP": "advanced",
        "EmitLLDP": "advanced",
        # Rest are expert (no tag)
    },
    # [Route] section
    "Route": {
        "Gateway": "basic",
        "Destination": "basic",
        "Metric": "basic",
        "Source": "advanced",
        "Scope": "advanced",
        "Type": "advanced",
        "Table": "advanced",
        "PreferredSource": "advanced",
        "OnLink": "advanced",
        "GatewayOnLink": "advanced",
    },
    # [Address] section
    "Address": {
        "Address": "basic",
        "Peer": "advanced",
        "Broadcast": "advanced",
        "Label": "advanced",
        "Scope": "advanced",
        "PreferredLifetime": "advanced",
    },
    # [DHCPv4] section
    "DHCPv4": {
        "UseDNS": "basic",
        "UseNTP": "basic",
        "UseHostname": "basic",
        "UseDomains": "advanced",
        "UseRoutes": "advanced",
        "UseGateway": "advanced",
        "UseMTU": "advanced",
        "UseTimezone": "advanced",
        "SendHostname": "advanced",
        "Hostname": "advanced",
        "ClientIdentifier": "advanced",
        "VendorClassIdentifier": "advanced",
        "RouteMetric": "advanced",
        "RouteTable": "advanced",
        "UseCaptivePortal": "advanced",
    },
    # [DHCPv6] section
    "DHCPv6": {
        "UseAddress": "basic",
        "UseDNS": "basic",
        "UseNTP": "basic",
        "UseHostname": "basic",
        "UseDelegatedPrefix": "advanced",
        "UseDomains": "advanced",
        "SendHostname": "advanced",
        "Hostname": "advanced",
        "PrefixDelegationHint": "advanced",
        "UseCaptivePortal": "advanced",
    },
}

# .link schema categories
LINK_SECTION_CATEGORIES = {
    "Match": "basic",
    "Link": "basic",
    "SR-IOV": "advanced",
}

LINK_PROPERTY_CATEGORIES = {
    "Match": {
        "OriginalName": "basic",
        "MACAddress": "basic",
        "PermanentMACAddress": "basic",
        "Type": "basic",
        "Driver": "advanced",
        "Path": "advanced",
        "Kind": "advanced",
        "Host": "advanced",
        "Virtualization": "advanced",
    },
    "Link": {
        "Name": "basic",
        "MACAddress": "basic",
        "MTUBytes": "basic",
        "Description": "basic",
        "Alias": "basic",
        "MACAddressPolicy": "advanced",
        "NamePolicy": "advanced",
        "AlternativeName": "advanced",
        "AlternativeNamesPolicy": "advanced",
        "WakeOnLan": "advanced",
        "WakeOnLanPassword": "advanced",
        "Port": "advanced",
        "Duplex": "advanced",
        "AutoNegotiation": "advanced",
        "BitsPerSecond": "advanced",
        "ReceiveChecksumOffload": "advanced",
        "TransmitChecksumOffload": "advanced",
        "GenericSegmentationOffload": "advanced",
        "TCPSegmentationOffload": "advanced",
        "TCP6SegmentationOffload": "advanced",
        "GenericReceiveOffload": "advanced",
        "LargeReceiveOffload": "advanced",
        # Rest are expert
    },
}

# .netdev schema categories
NETDEV_SECTION_CATEGORIES = {
    "Match": "basic",
    "NetDev": "basic",

    # Common virtual device types
    "Bridge": "advanced",
    "Bond": "advanced",
    "VLAN": "advanced",
    "VXLAN": "advanced",
    "Tunnel": "advanced",
    "IPIP": "advanced",
    "GRE": "advanced",
    "SIT": "advanced",
    "WireGuard": "advanced",
    "WireGuardPeer": "advanced",
    "VTI": "advanced",
    "VTI6": "advanced",
    "IP6GRE": "advanced",
    "IP6GRETAP": "advanced",
    "IP6Tunnel": "advanced",
    "GRETAP": "advanced",
    "VETH": "advanced",
    "TUN": "advanced",
    "TAP": "advanced",
    "Dummy": "advanced",
    "VRF": "advanced",

    # Expert/specialized
    "L2TP": None,
    "L2TPSession": None,
    "MACsec": None,
    "MACsecReceiveChannel": None,
    "MACsecTransmitAssociation": None,
    "MACsecReceiveAssociation": None,
    "MACVLAN": None,
    "MACVTAP": None,
    "IPVLAN": None,
    "IPVTAP": None,
    "GENEVE": None,
    "BareUDP": None,
    "BATADV": None,
    "IPoIB": None,
    "WLAN": None,
    "FOU": None,
    "ERSPAN": None,
    "Xfrm": None,
    "NetLabel": None,
    "Peer": None,
}

NETDEV_PROPERTY_CATEGORIES = {
    "Match": {
        "Host": "advanced",
        "Virtualization": "advanced",
    },
    "NetDev": {
        "Name": "basic",
        "Kind": "basic",
        "Description": "basic",
        "MTUBytes": "advanced",
        "MACAddress": "advanced",
    },
    "Bridge": {
        "STP": "basic",
        "ForwardDelay": "advanced",
        "HelloTime": "advanced",
        "MaxAge": "advanced",
        "AgeingTime": "advanced",
        "Priority": "advanced",
        "DefaultPVID": "advanced",
        "VLANFiltering": "advanced",
    },
    "Bond": {
        "Mode": "basic",
        "PrimaryReselectPolicy": "advanced",
        "MIIMonitorSec": "advanced",
        "UpDelaySec": "advanced",
        "DownDelaySec": "advanced",
        "ARPValidate": "advanced",
        "ARPIntervalSec": "advanced",
        "ARPAllTargets": "advanced",
        "TransmitHashPolicy": "advanced",
        "LACPTransmitRate": "advanced",
    },
    "VLAN": {
        "Id": "basic",
        "GVRP": "advanced",
        "MVRP": "advanced",
        "LooseBinding": "advanced",
        "ReorderHeader": "advanced",
    },
    "WireGuard": {
        "PrivateKey": "basic",
        "PrivateKeyFile": "basic",
        "ListenPort": "basic",
        "FirewallMark": "advanced",
        "RouteTable": "advanced",
        "RouteMetric": "advanced",
    },
    "WireGuardPeer": {
        "PublicKey": "basic",
        "AllowedIPs": "basic",
        "Endpoint": "basic",
        "PresharedKey": "advanced",
        "PresharedKeyFile": "advanced",
        "PersistentKeepalive": "advanced",
        "RouteTable": "advanced",
        "RouteMetric": "advanced",
    },
    "VXLAN": {
        "VNI": "basic",
        "Local": "advanced",
        "Remote": "advanced",
        "Group": "advanced",
        "DestinationPort": "advanced",
    },
    "Tunnel": {
        "Local": "basic",
        "Remote": "basic",
        "TTL": "advanced",
        "DiscoverPathMTU": "advanced",
    },
}


def apply_categories(schema: dict, section_categories: dict, property_categories: dict) -> dict:
    """Apply x-category to a schema based on the category definitions."""

    # Process top-level properties (sections like Match, Link, Network)
    if "properties" in schema:
        for section_name, section_def in schema["properties"].items():
            if section_name.startswith("_"):
                continue

            # Apply section-level category
            category = section_categories.get(section_name)
            if category:
                section_def["x-category"] = category

            # Apply property-level categories within the section
            if "properties" in section_def:
                prop_cats = property_categories.get(section_name, {})
                for prop_name, prop_def in section_def["properties"].items():
                    if prop_name.startswith("_"):
                        continue
                    if prop_name in prop_cats:
                        prop_def["x-category"] = prop_cats[prop_name]

    # Process definitions (section definitions like DHCPv4Section, RouteSection)
    if "definitions" in schema:
        for def_name, def_obj in schema["definitions"].items():
            if not def_name.endswith("Section"):
                continue

            # Map section definition name to section name
            section_name = def_name.replace("Section", "")

            # Apply section-level category
            category = section_categories.get(section_name)
            if category:
                def_obj["x-category"] = category

            # Apply property-level categories
            if "properties" in def_obj:
                prop_cats = property_categories.get(section_name, {})
                for prop_name, prop_def in def_obj["properties"].items():
                    if prop_name.startswith("_"):
                        continue
                    if prop_name in prop_cats:
                        prop_def["x-category"] = prop_cats[prop_name]

    return schema


def process_schema(input_path: Path, section_cats: dict, prop_cats: dict):
    """Process a single schema file."""
    print(f"Processing {input_path.name}...")

    with open(input_path, "r") as f:
        schema = json.load(f)

    schema = apply_categories(schema, section_cats, prop_cats)

    with open(input_path, "w") as f:
        json.dump(schema, f, indent=2)

    print(f"  Done: {input_path.name}")


def main():
    base_path = Path(__file__).parent.parent / "curated" / "v257"

    # Process .network schema
    network_path = base_path / "systemd.network.v257.schema.json"
    if network_path.exists():
        process_schema(network_path, NETWORK_SECTION_CATEGORIES, NETWORK_PROPERTY_CATEGORIES)

    # Process .link schema
    link_path = base_path / "systemd.link.v257.schema.json"
    if link_path.exists():
        process_schema(link_path, LINK_SECTION_CATEGORIES, LINK_PROPERTY_CATEGORIES)

    # Process .netdev schema
    netdev_path = base_path / "systemd.netdev.v257.schema.json"
    if netdev_path.exists():
        process_schema(netdev_path, NETDEV_SECTION_CATEGORIES, NETDEV_PROPERTY_CATEGORIES)

    print("\nAll schemas updated with x-category classifications.")


if __name__ == "__main__":
    main()
