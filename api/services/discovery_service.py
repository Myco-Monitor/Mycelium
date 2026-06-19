"""
Device Discovery and Registration Service for Mycelium

Discovers Spore and Hyphae devices on the local network via mDNS
(spore-NNNN.local / hyphae-NNNN.local) and registers them in the database.

Devices are reached by their mDNS hostname, not raw IP — the CSP TLS
certificates are issued for the mDNS hostname (+ the AP-mode IP), so an
HTTPS connection by LAN IP fails certificate validation. IP/CIDR scanning
was removed for this reason.
"""

import asyncio
import logging
import re
from typing import Dict, List, Any, Optional

from storage.tables.device_spore import (
    create_device_spore,
    get_device_spore_by_hostname,
    get_device_spore_by_mac,
)
from storage.tables.device_hyphae import (
    create_device_hyphae,
    get_device_hyphae_by_hostname,
    get_device_hyphae_by_mac,
)


class DeviceDiscoveryService:
    """
    Service for discovering and registering devices on the local network.

    Responsibilities:
    - Discovering devices via mDNS
    - Registering discovered devices in the database
    - Linking Spore devices to Hyphae controllers
    """

    def __init__(self):
        """Initialize the device discovery service."""
        self.logger = logging.getLogger("api.DeviceDiscoveryService")
        self.discovered_devices: Dict[str, Dict[str, Any]] = {}

    async def discover_mdns(self, timeout: float = 5.0) -> Dict[str, Dict[str, Any]]:
        """
        Discover MycoMonitor devices via mDNS.

        Looks for spore-NNNN.local and hyphae-NNNN.local hostnames
        using the zeroconf library.

        Args:
            timeout: How long to listen for mDNS responses (seconds).

        Returns:
            Dict of discovered devices keyed by hostname.
        """
        try:
            from zeroconf import Zeroconf, ServiceBrowser, ServiceListener
        except ImportError:
            self.logger.warning("zeroconf not installed, skipping mDNS discovery")
            return {}

        discovered: Dict[str, Dict[str, Any]] = {}

        class MyListener(ServiceListener):
            def add_service(self, zc, type_, name):
                info = zc.get_service_info(type_, name)
                if info is None:
                    return
                hostname = name.split(".")[0]
                # Match spore-NNNN or hyphae-NNNN
                if re.match(r"spore-\d{4}$", hostname):
                    device_type = "spore"
                elif re.match(r"hyphae-\d{4}$", hostname):
                    device_type = "hyphae"
                else:
                    return

                # Require a resolved address to confirm the service is live,
                # but address devices by mDNS hostname (not the raw IP).
                if info.parsed_addresses():
                    discovered[hostname] = {
                        "device_type": device_type,
                        "hostname": f"{hostname}.local",
                        "device_name": hostname,
                        "port": info.port,
                        "discovered_via": "mdns",
                    }

            def remove_service(self, zc, type_, name):
                pass

            def update_service(self, zc, type_, name):
                pass

        zc = Zeroconf()
        listener = MyListener()
        # Browse for HTTPS services
        browser = ServiceBrowser(zc, "_https._tcp.local.", listener)

        await asyncio.sleep(timeout)

        browser.cancel()
        zc.close()

        self.logger.info(f"mDNS discovery found {len(discovered)} devices")
        self.discovered_devices.update(discovered)
        return discovered

    async def register_devices(
        self, devices: Dict[str, Dict[str, Any]], room_id: int
    ) -> Dict[str, List[int]]:
        """
        Register discovered devices in the database.

        Args:
            devices (Dict[str, Dict[str, Any]]): Dictionary of discovered devices by hostname
            room_id (int): ID of the room to register the devices in

        Returns:
            Dict[str, List[int]]: Dictionary of registered device IDs by device type
        """
        registered_devices = {"spore": [], "hyphae": []}

        for device in devices.values():
            device_type = device.get("device_type")

            if device_type == "spore":
                device_id = await self._register_spore_device(device, room_id)
                if device_id:
                    registered_devices["spore"].append(device_id)
            elif device_type == "hyphae":
                device_id = await self._register_hyphae_device(device, room_id)
                if device_id:
                    registered_devices["hyphae"].append(device_id)

        return registered_devices

    async def _register_spore_device(
        self, device: Dict[str, Any], room_id: int
    ) -> Optional[int]:
        """
        Register a Spore device in the database.

        Args:
            device (Dict[str, Any]): Device information
            room_id (int): ID of the room to register the device in

        Returns:
            Optional[int]: ID of the registered device, or None if registration failed
        """
        try:
            hostname = device["hostname"]
            mac_address = device.get("mac_address", "")
            device_name = device.get("device_name", hostname)
            firmware_version = device.get("firmware_version", "")

            # Check if the device already exists
            existing_device = None
            if mac_address:
                existing_device = get_device_spore_by_mac(mac_address)

            if not existing_device:
                existing_device = get_device_spore_by_hostname(hostname)

            if existing_device:
                self.logger.info(
                    f"Spore device already registered: {device_name} ({hostname})"
                )
                return existing_device["device_id"]

            # Register the device
            device_id = create_device_spore(
                room_id=room_id,
                device_name=device_name,
                hostname=hostname,
                mac_address=mac_address,
                firmware_version=firmware_version,
                is_online=1,
            )

            self.logger.info(
                f"Registered Spore device: {device_name} ({hostname}) with ID {device_id}"
            )

            return device_id
        except Exception as e:
            self.logger.error(f"Error registering Spore device: {e}")
            return None

    async def _register_hyphae_device(
        self, device: Dict[str, Any], room_id: int
    ) -> Optional[int]:
        """
        Register a Hyphae device in the database.

        Args:
            device (Dict[str, Any]): Device information
            room_id (int): ID of the room to register the device in

        Returns:
            Optional[int]: ID of the registered device, or None if registration failed
        """
        try:
            hostname = device["hostname"]
            mac_address = device.get("mac_address", "")
            device_name = device.get("device_name", hostname)
            firmware_version = device.get("firmware_version", "")

            # Check if the device already exists
            existing_device = None
            if mac_address:
                existing_device = get_device_hyphae_by_mac(mac_address)

            if not existing_device:
                existing_device = get_device_hyphae_by_hostname(hostname)

            if existing_device:
                self.logger.info(
                    f"Hyphae device already registered: {device_name} ({hostname})"
                )
                return existing_device["device_id"]

            # Register the device
            device_id = create_device_hyphae(
                room_id=room_id,
                device_name=device_name,
                hostname=hostname,
                mac_address=mac_address,
                firmware_version=firmware_version,
                is_online=1,
            )

            self.logger.info(
                f"Registered Hyphae device: {device_name} ({hostname}) with ID {device_id}"
            )

            return device_id
        except Exception as e:
            self.logger.error(f"Error registering Hyphae device: {e}")
            return None

    async def link_spore_to_hyphae(self, spore_id: int, hyphae_id: int) -> bool:
        """
        Link a Spore device to a Hyphae device.

        Args:
            spore_id (int): ID of the Spore device
            hyphae_id (int): ID of the Hyphae device

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            from storage.tables.device_spore import update_device_spore_hyphae

            # Update the Spore device with the Hyphae ID
            update_device_spore_hyphae(spore_id, hyphae_id, 1)

            self.logger.info(
                f"Linked Spore device {spore_id} to Hyphae device {hyphae_id}"
            )

            return True
        except Exception as e:
            self.logger.error(f"Error linking Spore to Hyphae: {e}")
            return False
