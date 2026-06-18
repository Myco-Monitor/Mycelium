"""
Device Discovery and Registration Service for Mycelium

This module provides services for discovering and registering Spore and Hyphae devices
on the local network, including:
- Network scanning for devices
- Device identification and validation
- Device registration and configuration
"""

import asyncio
import logging
import socket
import ssl
import ipaddress
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set
from datetime import datetime

import aiohttp
from aiohttp import ClientTimeout

from api.clients.spore_client import SporeClient
from api.clients.hyphae_client import HyphaeClient
from api.clients.base_client import _CA_CERT_PATH
from storage.tables.device_spore import create_device_spore, get_device_spore_by_ip, get_device_spore_by_mac
from storage.tables.device_hyphae import create_device_hyphae, get_device_hyphae_by_ip, get_device_hyphae_by_mac

class DeviceDiscoveryService:
    """
    Service for discovering and registering devices on the local network.
    
    This service is responsible for:
    - Scanning the local network for devices
    - Identifying device types (Spore, Hyphae)
    - Registering devices in the database
    - Configuring newly discovered devices
    """
    
    # Device identification patterns
    SPORE_PATTERNS = [
        r"spore",
        r"sensor",
        r"myco.*sensor"
    ]
    
    HYPHAE_PATTERNS = [
        r"hyphae",
        r"controller",
        r"myco.*controller"
    ]
    
    def __init__(self):
        """Initialize the device discovery service."""
        self.logger = logging.getLogger("api.DeviceDiscoveryService")
        self.scan_in_progress = False
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
                hostname = name.split('.')[0]
                # Match spore-NNNN or hyphae-NNNN
                if re.match(r'spore-\d{4}$', hostname):
                    device_type = 'spore'
                elif re.match(r'hyphae-\d{4}$', hostname):
                    device_type = 'hyphae'
                else:
                    return

                addresses = info.parsed_addresses()
                ip = addresses[0] if addresses else None
                if ip:
                    discovered[hostname] = {
                        'device_type': device_type,
                        'ip_address': ip,
                        'hostname': f'{hostname}.local',
                        'device_name': hostname,
                        'port': info.port,
                        'discovered_via': 'mdns',
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

    async def scan_network(
        self,
        network: str,
        port: int = 443,
        timeout: float = 0.5,
        concurrent_scans: int = 20
    ) -> Dict[str, Dict[str, Any]]:
        """
        Scan the network for devices.
        
        Args:
            network (str): Network to scan in CIDR notation (e.g., "192.168.1.0/24")
            port (int): Port to scan
            timeout (float): Timeout for each connection attempt in seconds
            concurrent_scans (int): Number of concurrent scans
            
        Returns:
            Dict[str, Dict[str, Any]]: Dictionary of discovered devices by IP address
        """
        if self.scan_in_progress:
            self.logger.warning("Network scan already in progress")
            return self.discovered_devices
            
        self.scan_in_progress = True
        self.discovered_devices = {}
        
        try:
            # Parse the network
            network_obj = ipaddress.ip_network(network)
            
            # Create a list of all IP addresses in the network
            ip_addresses = [str(ip) for ip in network_obj.hosts()]
            
            self.logger.info(f"Scanning {len(ip_addresses)} IP addresses on network {network}")
            
            # Create a semaphore to limit concurrent scans
            semaphore = asyncio.Semaphore(concurrent_scans)
            
            # Create tasks for scanning each IP address
            tasks = []
            for ip in ip_addresses:
                task = asyncio.create_task(self._scan_ip(ip, port, timeout, semaphore))
                tasks.append(task)
                
            # Wait for all tasks to complete
            await asyncio.gather(*tasks)
            
            self.logger.info(f"Discovered {len(self.discovered_devices)} devices")
            
            return self.discovered_devices
        except Exception as e:
            self.logger.error(f"Error scanning network: {e}")
            return {}
        finally:
            self.scan_in_progress = False
            
    async def _scan_ip(
        self, 
        ip: str, 
        port: int, 
        timeout: float,
        semaphore: asyncio.Semaphore
    ) -> None:
        """
        Scan a single IP address for a device.
        
        Args:
            ip (str): IP address to scan
            port (int): Port to scan
            timeout (float): Timeout for the connection attempt in seconds
            semaphore (asyncio.Semaphore): Semaphore to limit concurrent scans
        """
        async with semaphore:
            try:
                # Try to connect to the IP address
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(ip, port),
                    timeout=timeout
                )
                
                # If we get here, the connection was successful
                writer.close()
                await writer.wait_closed()
                
                # Try to identify the device
                device_info = await self._identify_device(ip, port)
                
                if device_info:
                    self.discovered_devices[ip] = device_info
                    self.logger.info(f"Discovered device at {ip}: {device_info['device_type']} - {device_info.get('device_name', 'Unknown')}")
            except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
                # No device at this IP address or port
                pass
            except Exception as e:
                self.logger.debug(f"Error scanning {ip}: {e}")
                
    async def _identify_device(self, ip: str, port: int) -> Optional[Dict[str, Any]]:
        """
        Identify a device at the given IP address.
        
        Args:
            ip (str): IP address of the device
            port (int): Port of the device
            
        Returns:
            Optional[Dict[str, Any]]: Device information if identified, None otherwise
        """
        # Determine protocol based on port
        protocol = "https" if port == 443 else "http"

        # Try to identify as a Spore device
        try:
            client = SporeClient(base_url=f"{protocol}://{ip}", device_name=f"scan-{ip}", device_id=0, use_tls=(protocol == "https"))
            info = await client.get_info()

            # Check if this looks like a Spore device
            if info and self._is_spore_device(info):
                return {
                    "device_type": "spore",
                    "ip_address": ip,
                    "mac_address": info.get("mac_address", ""),
                    "device_name": info.get("device_name", f"Spore-{ip.split('.')[-1]}"),
                    "firmware_version": info.get("firmware_version", ""),
                    "info": info
                }
        except Exception as e:
            self.logger.debug(f"Error identifying Spore device at {ip}: {e}")

        # Try to identify as a Hyphae device
        try:
            client = HyphaeClient(base_url=f"{protocol}://{ip}", device_name=f"scan-{ip}", device_id=0, use_tls=(protocol == "https"))
            info = await client.get_info()

            # Check if this looks like a Hyphae device
            if info and self._is_hyphae_device(info):
                return {
                    "device_type": "hyphae",
                    "ip_address": ip,
                    "mac_address": info.get("mac_address", ""),
                    "device_name": info.get("device_name", f"Hyphae-{ip.split('.')[-1]}"),
                    "firmware_version": info.get("firmware_version", ""),
                    "info": info
                }
        except Exception as e:
            self.logger.debug(f"Error identifying Hyphae device at {ip}: {e}")
            
        # Try to identify by making a generic HTTPS request
        try:
            from api.clients.base_client import create_device_ssl_context
            ssl_ctx = create_device_ssl_context()
            connector = aiohttp.TCPConnector(ssl=ssl_ctx)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(
                    f"https://{ip}",
                    timeout=ClientTimeout(total=2)
                ) as response:
                    if response.status == 200:
                        content = await response.text()
                        
                        # Check if the content matches any device patterns
                        if any(re.search(pattern, content, re.IGNORECASE) for pattern in self.SPORE_PATTERNS):
                            return {
                                "device_type": "spore",
                                "ip_address": ip,
                                "device_name": f"Spore-{ip.split('.')[-1]}",
                                "info": {"html_content": content[:100] + "..."}
                            }
                        elif any(re.search(pattern, content, re.IGNORECASE) for pattern in self.HYPHAE_PATTERNS):
                            return {
                                "device_type": "hyphae",
                                "ip_address": ip,
                                "device_name": f"Hyphae-{ip.split('.')[-1]}",
                                "info": {"html_content": content[:100] + "..."}
                            }
        except Exception as e:
            self.logger.debug(f"Error making generic request to {ip}: {e}")
            
        # If we get here, we couldn't identify the device
        return None
        
    def _is_spore_device(self, info: Dict[str, Any]) -> bool:
        """
        Check if the device info matches a Spore device.

        Args:
            info (Dict[str, Any]): Device information

        Returns:
            bool: True if the device is a Spore device, False otherwise
        """
        # Check for Spore-specific fields
        if "device_type" in info and info["device_type"].lower() == "spore":
            return True

        # Check for warmup_state field (Spore-specific from /api/status)
        if "warmup_state" in info:
            return True

        # Check for sensor-related fields
        if "sensors" in info:
            return True

        # Check the device name
        if "device_name" in info:
            return any(re.search(pattern, info["device_name"], re.IGNORECASE) for pattern in self.SPORE_PATTERNS)

        return False
        
    def _is_hyphae_device(self, info: Dict[str, Any]) -> bool:
        """
        Check if the device info matches a Hyphae device.

        Args:
            info (Dict[str, Any]): Device information

        Returns:
            bool: True if the device is a Hyphae device, False otherwise
        """
        # Check for Hyphae-specific fields
        if "device_type" in info and info["device_type"].lower() == "hyphae":
            return True

        # Check for wifi_rssi field (Hyphae-specific from /api/system/info)
        if "wifi_rssi" in info:
            return True

        # Check for relay-related fields
        if "relays" in info:
            return True

        # Check the device name
        if "device_name" in info:
            return any(re.search(pattern, info["device_name"], re.IGNORECASE) for pattern in self.HYPHAE_PATTERNS)

        return False
        
    async def register_devices(
        self, 
        devices: Dict[str, Dict[str, Any]], 
        room_id: int
    ) -> Dict[str, List[int]]:
        """
        Register discovered devices in the database.
        
        Args:
            devices (Dict[str, Dict[str, Any]]): Dictionary of discovered devices by IP address
            room_id (int): ID of the room to register the devices in
            
        Returns:
            Dict[str, List[int]]: Dictionary of registered device IDs by device type
        """
        registered_devices = {
            "spore": [],
            "hyphae": []
        }
        
        for ip, device in devices.items():
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
        self, 
        device: Dict[str, Any], 
        room_id: int
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
            ip_address = device["ip_address"]
            mac_address = device.get("mac_address", "")
            device_name = device.get("device_name", f"Spore-{ip_address.split('.')[-1]}")
            firmware_version = device.get("firmware_version", "")
            
            # Check if the device already exists
            existing_device = None
            if mac_address:
                existing_device = get_device_spore_by_mac(mac_address)
            
            if not existing_device:
                existing_device = get_device_spore_by_ip(ip_address)
                
            if existing_device:
                self.logger.info(f"Spore device already registered: {device_name} ({ip_address})")
                return existing_device["device_id"]
                
            # Register the device
            device_id = create_device_spore(
                room_id=room_id,
                device_name=device_name,
                ip_address=ip_address,
                mac_address=mac_address,
                firmware_version=firmware_version,
                is_online=1
            )
            
            self.logger.info(f"Registered Spore device: {device_name} ({ip_address}) with ID {device_id}")
            
            return device_id
        except Exception as e:
            self.logger.error(f"Error registering Spore device: {e}")
            return None
            
    async def _register_hyphae_device(
        self, 
        device: Dict[str, Any], 
        room_id: int
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
            ip_address = device["ip_address"]
            mac_address = device.get("mac_address", "")
            device_name = device.get("device_name", f"Hyphae-{ip_address.split('.')[-1]}")
            firmware_version = device.get("firmware_version", "")
            
            # Check if the device already exists
            existing_device = None
            if mac_address:
                existing_device = get_device_hyphae_by_mac(mac_address)
            
            if not existing_device:
                existing_device = get_device_hyphae_by_ip(ip_address)
                
            if existing_device:
                self.logger.info(f"Hyphae device already registered: {device_name} ({ip_address})")
                return existing_device["device_id"]
                
            # Register the device
            device_id = create_device_hyphae(
                room_id=room_id,
                device_name=device_name,
                ip_address=ip_address,
                mac_address=mac_address,
                firmware_version=firmware_version,
                is_online=1
            )
            
            self.logger.info(f"Registered Hyphae device: {device_name} ({ip_address}) with ID {device_id}")
            
            return device_id
        except Exception as e:
            self.logger.error(f"Error registering Hyphae device: {e}")
            return None
            
    async def link_spore_to_hyphae(
        self, 
        spore_id: int, 
        hyphae_id: int
    ) -> bool:
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
            
            self.logger.info(f"Linked Spore device {spore_id} to Hyphae device {hyphae_id}")
            
            return True
        except Exception as e:
            self.logger.error(f"Error linking Spore to Hyphae: {e}")
            return False
