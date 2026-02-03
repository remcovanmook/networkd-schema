#!/bin/bash
# /etc/network/scripts/cake-qos.sh
# ADVANCED: QoS (CAKE) - MANUAL TC SCRIPT
#
# While systemd-networkd supports [QDisc], this script demonstrates
# how to apply CAKE manually using the `tc` command.
#
# Can be invoked via a systemd service or ExecStartPost= in .network file.

IFACE="wan0"
BANDWIDTH="100mbit"

# Clear existing qdiscs
tc qdisc del dev $IFACE root 2>/dev/null

# Apply CAKE to root
tc qdisc add dev $IFACE root handle 1: cake bandwidth $BANDWIDTH
