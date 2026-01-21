import json
import re

files = [
    '/Users/remco/networkd-schema/curated/systemd.network.v257.schema.json',
    '/Users/remco/networkd-schema/curated/systemd.netdev.v257.schema.json',
    '/Users/remco/networkd-schema/curated/systemd.link.v257.schema.json'
]

# Context-aware overrides: (Section/Parent, Property) -> Metadata
# If Section is None, applies globally if not overridden.
CONTEXT_OVERRIDES = {
    ("Match", "MACAddress"): {
        "title": "MAC Address Match",
        "description": "A whitespace-separated list of hardware addresses.",
        "examples": ["12:34:56:78:9a:bc", "00:11:22:33:44:55 66:77:88:99:aa:bb"]
    },
    ("Link", "MACAddress"): {
        "title": "Set MAC Address",
        "examples": ["12:34:56:78:9a:bc", "none"]
    },
    ("NetDev", "MACAddress"): {
        "title": "MAC Address",
        "examples": ["12:34:56:78:9a:bc", "none"]
    }
}

# Global Property Metadata (Title, Examples) derived from Man Pages
GLOBAL_METADATA = {
    "DHCP": {"title": "DHCP Client", "examples": ["yes", "no", "ipv4", "ipv6"]},
    "DHCPServer": {"title": "DHCP Server", "examples": ["yes", "no"]},
    "LinkLocalAddressing": {"title": "Link-Local Addressing", "examples": ["yes", "no", "ipv4", "ipv6"]},
    "IPv6LinkLocalAddressGenerationMode": {"title": "IPv6 LLC Addr Gen Mode", "examples": ["eui64", "none", "stable-privacy", "random"]},
    "IPv6AcceptRA": {"title": "IPv6 Accept RA", "examples": ["yes", "no"]},
    "IPv6SendRA": {"title": "IPv6 Send RA", "examples": ["yes", "no"]},
    "Description": {"title": "Description", "examples": ["My Interface", "Uplink to ISP"]},
    "Name": {"title": "Interface Name", "examples": ["eth0", "br0"]},
    "Kind": {"title": "NetDev Kind", "examples": ["bridge", "bond", "vlan", "veth"]},
    "MTUBytes": {"title": "MTU (Bytes)", "examples": ["1500", "9000", "auto"]},
    "ARP": {"title": "ARP", "examples": ["yes", "no"]},
    "Multicast": {"title": "Multicast", "examples": ["yes", "no"]},
    "AllMulticast": {"title": "All Multicast", "examples": ["yes", "no"]},
    "Promiscuous": {"title": "Promiscuous Mode", "examples": ["yes", "no"]},
    "Unmanaged": {"title": "Unmanaged", "examples": ["yes", "no"]},
    "RequiredForOnline": {"title": "Required For Online", "examples": ["yes", "no", "carrier", "degraded:routable"]},
    "ActivationPolicy": {"title": "Activation Policy", "examples": ["up", "always-up", "bound", "manual", "down", "always-down"]},
    "RequiredFamilyForOnline": {"title": "Required Family For Online", "examples": ["yes", "no", "ipv4", "ipv6", "both", "any"]},
    "Gateway": {"title": "Gateway", "examples": ["192.168.1.1", "fe80::1"]},
    "DNS": {"title": "DNS Servers", "examples": ["8.8.8.8", "2001:4860:4860::8888"]},
    "Domains": {"title": "Search Domains", "examples": ["example.com", "~."]},
    "NTP": {"title": "NTP Servers", "examples": ["pool.ntp.org"]},
    "VLANId": {"title": "VLAN ID", "examples": [1, 100, 4094]},
    "Priority": {"title": "Priority", "examples": [100, 20]},
    "Weight": {"title": "Weight", "examples": [100]},
    "Type": {"title": "Type", "examples": ["global", "link", "host"]}, # Route type or others
    "Scope": {"title": "Scope", "examples": ["global", "link", "host"]},
    "Protocol": {"title": "Protocol", "examples": ["kernel", "boot", "static"]},
    "Table": {"title": "Routing Table", "examples": ["main", "local", "default", 100]},
    "Destination": {"title": "Destination", "examples": ["0.0.0.0/0", "192.168.1.0/24", "::/0"]},
    "Source": {"title": "Source", "examples": ["192.168.1.5"]},
    "PreferredSource": {"title": "Preferred Source", "examples": ["192.168.1.5"]},
    "MACsec": {"title": "MACsec"},
    "L2TP": {"title": "L2TP"},
    "IPoIB": {"title": "IPoIB"},
    "CAN": {"title": "CAN"},
    "WLAN": {"title": "WLAN"},
    "VXLAN": {"title": "VXLAN"},
    "WWAN": {"title": "WWAN"},
}

# Heuristic fallback
def camel_to_title(name):
    s = re.sub(r'(.)([A-Z][a-z]+)', r'\1 \2', name)
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', s)
    return s

def process_properties(props, parent_path):
    for name, schema in props.items():
        current_path = parent_path + [name]
        
        # Determine Context (Section)
        # Filter out "properties" from path to get logical structure
        # e.g. ["Match", "properties", "MACAddress"] -> ["Match", "MACAddress"]
        logical_path = [x for x in current_path if x != "properties"]
        
        section = None
        if len(logical_path) >= 2:
            section = logical_path[-2]
        
        # Apply Overrides
        updated = False
        
        # 1. Context Specific Override
        if section and (section, name) in CONTEXT_OVERRIDES:
            meta = CONTEXT_OVERRIDES[(section, name)]
            for k, v in meta.items():
                schema[k] = v
            updated = True
            
        # 2. Global Override (if not fully handled or to augment)
        if not updated and name in GLOBAL_METADATA:
            meta = GLOBAL_METADATA[name]
            for k, v in meta.items():
                if k not in schema: # Don't overwrite if context specific set it (though we didn't set it if updated=False)
                     schema[k] = v
            updated = True
            
        # 3. Fallback Title
        if "title" not in schema:
            schema["title"] = camel_to_title(name)
            
        # Recurse
        if schema.get("type") == "object" and "properties" in schema:
            process_properties(schema["properties"], current_path + ["properties"])

def process_file(path):
    with open(path, 'r') as f:
        data = json.load(f)
    
    if "properties" in data:
        process_properties(data["properties"], [])

    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"Processed {path}")

for p in files:
    try:
        process_file(p)
    except Exception as e:
        print(f"Error processing {p}: {e}")
