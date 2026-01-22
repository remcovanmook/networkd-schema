import json
import re
import os

files = [
    '/Users/remco/networkd-schema/curated/v257/systemd.network.v257.schema.json',
    '/Users/remco/networkd-schema/curated/v257/systemd.netdev.v257.schema.json',
    '/Users/remco/networkd-schema/curated/v257/systemd.link.v257.schema.json'
]

VSCODE_HINT_DIR = '/Users/remco/networkd-schema/deps/vscode-systemd/src/hint-data/manifests'

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

def camel_to_title(name):
    s = re.sub(r'(.)([A-Z][a-z]+)', r'\1 \2', name)
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', s)
    # Fix for IPv4/IPv6 being split as I Pv4/I Pv6
    s = s.replace("I Pv", "IPv")
    return s


# --- VSCode Hint Data Loading ---

HINT_CACHE = {} # Cache loaded hint data

def load_hints(schema_type):
    """Loads and parses the vscode-systemd hint manifest for the given type (network/netdev)."""
    if schema_type in HINT_CACHE:
        return HINT_CACHE[schema_type]

    filename = f"{schema_type}.json"
    path = os.path.join(VSCODE_HINT_DIR, filename)
    
    if not os.path.exists(path):
        print(f"Warning: Hint file not found: {path}")
        return {}

    try:
        with open(path, 'r') as f:
            raw_data = json.load(f)
    except Exception as e:
        print(f"Error loading {path}: {e}")
        return {}

    # Parse Manifest
    # Type 2: [2, "DirectiveName", signature, docsIndex, manPageIndex, sectionIndex]
    # Type 4: [4, index, "Markdown", urlRefId, sinceVersion?]
    
    docs_map = {} # index -> markdown
    directives = {} # name -> { markdown, since }

    # First pass: Collect docs
    for item in raw_data:
        if item[0] == 4: # DocsMarkdown
            idx = item[1]
            markdown = item[2]
            # item[3] is urlRefId
            since = item[4] if len(item) > 4 else None
            # Normalize markdown?
            docs_map[idx] = {"md": markdown, "since": since}

    # Second pass: Map directives
    for item in raw_data:
        if item[0] == 2: # Directive
            name = item[1]
            docs_idx = item[3]
            
            if docs_idx in docs_map:
                directives[name] = docs_map[docs_idx]
            else:
                 directives[name] = {"md": "", "since": None}

    HINT_CACHE[schema_type] = directives
    return directives

def extract_deprecation(markdown):
    """
    Analyzes markdown text for deprecation warnings.
    Returns None or { description, replaced_by, since }
    """
    if not markdown:
        return None
        
    lower_md = markdown.lower()
    if "deprecated" not in lower_md:
        return None
        
    # Extract simple description (first sentence containing 'deprecated' or the whole paragraph?)
    # For now, let's grab the sentence containing "deprecated"
    sentences = re.split(r'(?<=[.!?])\s+', markdown)
    dep_sentence = next((s for s in sentences if "deprecated" in s.lower()), None)
    
    if not dep_sentence:
        return None

    # Filter out partial deprecations (e.g. "values ... are deprecated")
    lower_dep = dep_sentence.lower()
    
    # Heuristics for "value deprecation" vs "property deprecation"
    # "values ... are deprecated"
    # "is deprecated ... values"
    # "boolean values ... deprecated"
    if "values" in lower_dep or ("setting" in lower_dep and "to" in lower_dep):
         # Likely mentioning a specific setting value or a range of values
         return None

    # Try to find replacement

    # Patterns: "Use X instead", "Superseded by X", "Please use X"
    replaced_by = None
    
    # Look for `Name=` pattern or just Name
    # Regex 1: "use `?(\w+)=?`? instead"
    match = re.search(r'use (?:the )?`?([A-Z][a-zA-Z0-9]+)=?`? instead', markdown, re.IGNORECASE)
    if match:
        replaced_by = match.group(1)
    
    if not replaced_by:
        match = re.search(r'superseded by `?([A-Z][a-zA-Z0-9]+)=?`?', markdown, re.IGNORECASE)
        if match:
             replaced_by = match.group(1)

    return {
        "description": dep_sentence.strip(),
        "replaced_by": replaced_by
    }


# --- Schema Processing ---

# Section Dependencies (Root Level)
SIMPLE_DEPENDENCIES = {
    # Core
    "Link": ["Match"],
    "Network": ["Match"],
    "Address": ["Match"],
    "Route": ["Match"],
    
    # Bridge Sub-sections
    "BridgeFDB": ["Network"], 
    "BridgeMDB": ["Network"],
    "BridgeVLAN": ["Network"],
    
    # QDisc / Traffic Control
    "QDisc": ["Network"],
    "TrafficControlQueueingDiscipline": ["Network"],
    "BFIFO": ["Network"],
    "CAKE": ["Network"],
    "ControlledDelay": ["Network"],
    "DeficitRoundRobinScheduler": ["Network"],
    "DeficitRoundRobinSchedulerClass": ["Network"],
    "EnhancedTransmissionSelection": ["Network"],
    "PFIFO": ["Network"],
    "PFIFOFast": ["Network"],
    "PFIFOHeadDrop": ["Network"],
    "QuickFairQueueing": ["Network"],
    "QuickFairQueueingClass": ["Network"],
    "FairQueueing": ["Network"],
    "FairQueueingControlledDelay": ["Network"],
    "FlowQueuePIE": ["Network"],
    "GenericRandomEarlyDetection": ["Network"],
    "HeavyHitterFilter": ["Network"],
    "HierarchyTokenBucket": ["Network"],
    "HierarchyTokenBucketClass": ["Network"],
    "ClassfulMultiQueueing": ["Network"],
    "BandMultiQueueing": ["Network"],
    "NetworkEmulator": ["Network"],
    "PIE": ["Network"],
    "StochasticFairBlue": ["Network"],
    "StochasticFairnessQueueing": ["Network"],
    "TokenBucketFilter": ["Network"],
    "TrivialLinkEqualizer": ["Network"],
    
    # Other
    "NextHop": ["Network"],
    "RoutingPolicyRule": ["Network"]
}

# Complex: Presence of Section A requires Presence of Section B AND specific property in B
COMPLEX_DEPENDENCIES = {
    "IPoIB": {
        "required": ["Network"],
        "properties": { "Network": { "required": ["IPoIB"] } }
    },
    "DHCPServer": {
         "required": ["Network"],
         "properties": { "Network": { "required": ["DHCPServer"] } }
    },
     "IPv6SendRA": {
         "required": ["Network"],
         "properties": { "Network": { "required": ["IPv6SendRA"] } }
    },
    "IPv6AcceptRA": {
         "required": ["Network"],
         "properties": { "Network": { "required": ["IPv6AcceptRA"] } }
    },
    "Bridge": {
        "required": ["Network"],
        "properties": { "Network": { "required": ["Bridge"] } }
    },
    "CAN": {
        "required": ["Network"],
        "properties": { "Network": { "required": ["CAN"] } }
    },
    "DHCPv4": {
        "required": ["Network"],
        "properties": { "Network": { "required": ["DHCP"] } }
    },
    "DHCPv6": {
        "required": ["Network"],
        "properties": { "Network": { "required": ["DHCP"] } }
    },
    
    # --- NetDev Dependencies (Kind-based) ---
    "VLAN": {"required": ["NetDev"], "properties": {"NetDev": {"not": {"properties": {"Kind": {"not": {"const": "vlan"}}}}}}},
    "MACVLAN": {"required": ["NetDev"], "properties": {"NetDev": {"not": {"properties": {"Kind": {"not": {"const": "macvlan"}}}}}}},
    "MACVTAP": {"required": ["NetDev"], "properties": {"NetDev": {"not": {"properties": {"Kind": {"not": {"const": "macvtap"}}}}}}},
    "IPVLAN": {"required": ["NetDev"], "properties": {"NetDev": {"not": {"properties": {"Kind": {"not": {"const": "ipvlan"}}}}}}},
    "IPVTAP": {"required": ["NetDev"], "properties": {"NetDev": {"not": {"properties": {"Kind": {"not": {"const": "ipvtap"}}}}}}},
    "VXLAN": {"required": ["NetDev"], "properties": {"NetDev": {"not": {"properties": {"Kind": {"not": {"const": "vxlan"}}}}}}},
    "GENEVE": {"required": ["NetDev"], "properties": {"NetDev": {"not": {"properties": {"Kind": {"not": {"const": "geneve"}}}}}}},
    "BareUDP": {"required": ["NetDev"], "properties": {"NetDev": {"not": {"properties": {"Kind": {"not": {"const": "bareudp"}}}}}}},
    "FooOverUDP": {"required": ["NetDev"], "properties": {"NetDev": {"not": {"properties": {"Kind": {"not": {"const": "fou"}}}}}}},
    "L2TP": {"required": ["NetDev"], "properties": {"NetDev": {"not": {"properties": {"Kind": {"not": {"const": "l2tp"}}}}}}},
    "L2TPSession": {"required": ["NetDev"], "properties": {"NetDev": {"not": {"properties": {"Kind": {"not": {"const": "l2tp"}}}}}}},
    "MACsec": {"required": ["NetDev"], "properties": {"NetDev": {"not": {"properties": {"Kind": {"not": {"const": "macsec"}}}}}}},
    "MACsecReceiveChannel": {"required": ["NetDev"], "properties": {"NetDev": {"not": {"properties": {"Kind": {"not": {"const": "macsec"}}}}}}},
    "MACsecTransmitAssociation": {"required": ["NetDev"], "properties": {"NetDev": {"not": {"properties": {"Kind": {"not": {"const": "macsec"}}}}}}},
    "MACsecReceiveAssociation": {"required": ["NetDev"], "properties": {"NetDev": {"not": {"properties": {"Kind": {"not": {"const": "macsec"}}}}}}},
    "Tun": {"required": ["NetDev"], "properties": {"NetDev": {"not": {"properties": {"Kind": {"not": {"const": "tun"}}}}}}},
    "Tap": {"required": ["NetDev"], "properties": {"NetDev": {"not": {"properties": {"Kind": {"not": {"const": "tap"}}}}}}},
    "Bond": {"required": ["NetDev"], "properties": {"NetDev": {"not": {"properties": {"Kind": {"not": {"const": "bond"}}}}}}},
    "Bridge": {"required": ["NetDev"], "properties": {"NetDev": {"not": {"properties": {"Kind": {"not": {"const": "bridge"}}}}}}},
    "VRF": {"required": ["NetDev"], "properties": {"NetDev": {"not": {"properties": {"Kind": {"not": {"const": "vrf"}}}}}}},
    "WireGuard": {"required": ["NetDev"], "properties": {"NetDev": {"not": {"properties": {"Kind": {"not": {"const": "wireguard"}}}}}}},
    "WireGuardPeer": {"required": ["NetDev"], "properties": {"NetDev": {"not": {"properties": {"Kind": {"not": {"const": "wireguard"}}}}}}},
    "BatmanAdvanced": {"required": ["NetDev"], "properties": {"NetDev": {"not": {"properties": {"Kind": {"not": {"const": "batman-adv"}}}}}}},
    "IPoIB": {"required": ["NetDev"], "properties": {"NetDev": {"not": {"properties": {"Kind": {"not": {"const": "ipoib"}}}}}}},
    "WLAN": {"required": ["NetDev"], "properties": {"NetDev": {"not": {"properties": {"Kind": {"not": {"const": "wlan"}}}}}}},
    "Tunnel": {"required": ["NetDev"], "properties": {"NetDev": {"required": ["Kind"]}}}
}

PROPERTY_CATEGORIES = {
    "Network": {
        "Addressing": ["Address", "Gateway", "DNS", "Domains", "NTP"],
        "Routing": ["IPForwarding", "IPMasquerade", "IPv4Forwarding", "IPv6Forwarding"],
        "Link Configuration": ["MACAddress", "MTUBytes", "LinkLocalAddressing"],
        "DHCP/IPv6": ["DHCP", "DHCPServer", "IPv6AcceptRA", "IPv6SendRA"]
    },
    "Match": {
        "Hardware": ["MACAddress", "Path", "Driver", "Type"],
        "Network": ["Name", "WLANInterfaceType", "SSID"],
        "Virtualization": ["Virtualization", "Container", "Kind"]
    },
    "Link": {
        "Hardware": ["MACAddress", "MTUBytes"],
        "Offload": ["TCPSegmentationOffload", "GenericSegmentationOffload", "LargeReceiveOffload", "GenericReceiveOffload"]
    },
    "NetDev": {
        "Identity": ["Name", "Kind", "Description"],
        "Hardware": ["MACAddress", "MTUBytes"]
    },
    "VLAN": {
        "Configuration": ["Id"]
    },
    "VXLAN": {
        "Configuration": ["VNI", "DestinationPort", "Local", "Remote", "Group"]
    },
    "WireGuard": {
        "Configuration": ["PrivateKey", "PrivateKeyFile", "ListenPort", "FirewallMark"]
    },
    "WireGuardPeer": {
        "Configuration": ["PublicKey", "PresharedKey", "PresharedKeyFile", "Endpoint", "AllowedIPs"]
    }
}

REQUIRED_FIELDS = {
    # Network
    "Address": ["Address"],
    "IPv6AddressLabel": ["Label", "Prefix"],
    "BridgeFDB": ["MACAddress"],
    "BridgeMDB": ["MulticastGroupAddress"],
    "IPv6Prefix": ["Prefix"], 
    
    # NetDev
    "VLAN": ["Id"],
    "VXLAN": ["VNI"],
    "FooOverUDP": ["Port"],
    "L2TPSession": ["SessionId", "PeerSessionId"],
    "BareUDP": ["DestinationPort", "EtherType"],
    "L2TP": ["TunnelId", "PeerTunnelId", "Remote"],
    "WLAN": ["PhysicalDevice", "Type"],
    "Xfrm": ["InterfaceId"],
    "VRF": ["Table"]
}

def inject_dependencies(data):
    if "dependencies" not in data:
        data["dependencies"] = {}

    for section, deps in SIMPLE_DEPENDENCIES.items():
        if section in data.get("properties", {}):
            if section not in data["dependencies"]:
                 data["dependencies"][section] = deps

    for section, rule in COMPLEX_DEPENDENCIES.items():
        if section in data.get("properties", {}):
            data["dependencies"][section] = rule


def process_properties(props, parent_path, hints):
    for name, schema in props.items():
        current_path = parent_path + [name]
        
        logical_path = [x for x in current_path if x not in ["properties", "items", "oneOf"] and not x.isdigit()]
        
        section = None
        if len(logical_path) >= 2:
            section = logical_path[-2]
        
        # --- Overrides ---
        updated = False
        if section and (section, name) in CONTEXT_OVERRIDES:
            meta = CONTEXT_OVERRIDES[(section, name)]
            for k, v in meta.items():
                schema[k] = v
            updated = True
            
        if not updated and name in GLOBAL_METADATA:
            meta = GLOBAL_METADATA[name]
            for k, v in meta.items():
                if k not in schema: 
                     schema[k] = v
            updated = True
            
        if "title" not in schema or "I Pv" in schema.get("title", ""):
            schema["title"] = camel_to_title(name)

        # --- Subcategories ---
        if section and section in PROPERTY_CATEGORIES:
            for cat_name, prop_list in PROPERTY_CATEGORIES[section].items():
                if name in prop_list:
                    schema["x-subcategory"] = cat_name
                    break
                    
        # --- Deprecation from Hints ---
        # Idempotency: Clear previous deprecation status before re-evaluating
        if "deprecated" in schema:
            del schema["deprecated"]
        if "x-deprecation" in schema:
            del schema["x-deprecation"]
        
        # Clean up description (remove previously appended DEPRECATED note)
        if "description" in schema:
            schema["description"] = re.sub(r'\n\nDEPRECATED: .*', '', schema["description"], flags=re.DOTALL)

        if name in hints:
            hint = hints[name]
            dep_info = extract_deprecation(hint["md"])
            if dep_info:
                schema["deprecated"] = True
                
                # Build x-deprecation object
                x_dep = {
                    "description": dep_info["description"]
                }
                
                if dep_info["replaced_by"]:
                    x_dep["replaced_by"] = dep_info["replaced_by"] # Using replaced_by per user request
                    
                # If 'since' version was in the hint data (from Type 4 item, index 4), add it check hint["since"]
                # In parsed hints, we stored 'since' from item[4]
                if hint.get("since"):
                     x_dep["since"] = str(hint["since"])

                schema["x-deprecation"] = x_dep
                
                # Append to description for visibility
                desc = schema.get("description", "")
                note = f"\n\nDEPRECATED: {dep_info['description']}"
                if dep_info["replaced_by"]:
                    note += f" Use {dep_info['replaced_by']} instead."
                
                if note not in desc:
                    schema["description"] = desc + note

        # --- Explicit Requirements Injector ---
        if name in REQUIRED_FIELDS:
            reqs = REQUIRED_FIELDS[name]
            targets = []
            if schema.get("type") == "object":
                targets.append(schema)
            if "oneOf" in schema:
                for variant in schema["oneOf"]:
                    if variant.get("type") == "object":
                        targets.append(variant)
                    elif variant.get("type") == "array" and "items" in variant:
                        item_schema = variant["items"]
                        if item_schema.get("type") == "object":
                            targets.append(item_schema)
            for t in targets:
                if "required" not in t:
                    t["required"] = []
                for r in reqs:
                    if r not in t["required"]:
                        t["required"].append(r)

        # --- Recurse ---
        if schema.get("type") == "object" and "properties" in schema:
            process_properties(schema["properties"], current_path + ["properties"], hints)
        
        if "oneOf" in schema:
            for i, variant in enumerate(schema["oneOf"]):
                if variant.get("type") == "object" and "properties" in variant:
                    process_properties(variant["properties"], current_path + ["oneOf", str(i), "properties"], hints)
                elif variant.get("type") == "array" and "items" in variant:
                    item_schema = variant["items"]
                    if item_schema.get("type") == "object" and "properties" in item_schema:
                         process_properties(item_schema["properties"], current_path + ["oneOf", str(i), "items", "properties"], hints)

def process_file(path):
    with open(path, 'r') as f:
        data = json.load(f)
        
    # Determine type of schema for hints
    hints = {}
    if "network" in path:
        hints = load_hints("network")
    elif "netdev" in path:
        hints = load_hints("netdev")
    
    if "properties" in data:
        process_properties(data["properties"], [], hints)
    
    inject_dependencies(data)

    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"Processed {path}")

for p in files:
    try:
        process_file(p)
    except Exception as e:
        print(f"Error processing {p}: {e}")
