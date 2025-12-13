import os
import hashlib
import ipaddress

from aiohttp import web
from pathlib import Path


def get_ip(request: web.Request) -> str:
    """Extract IP address from request headers or remote address."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.headers.get("X-Real-IP")

    if not ip:
        ip = request.remote

    try:
        # Validate and normalize the IP address
        ip = str(ipaddress.ip_address(ip))
    except ValueError:
        ip = ""

    return ip


class IPFilter:
    def __init__(self, whitelist_file: str | Path, blacklist_file: str | Path):
        self.whitelist_file = whitelist_file
        self.blacklist_file = blacklist_file

        self._whitelist_hash = None
        self._blacklist_hash = None

        self.whitelist = []
        self.blacklist = []

        self.load_filter_list()

    @staticmethod
    def calculate_file_hash(filter_file) -> str:
        """Calculate the SHA256 hash of the filter IP list file."""
        if os.path.exists(filter_file):
            with open(filter_file, "rb") as f:
                file_data = f.read()
                return hashlib.sha256(file_data).hexdigest()
        return ""

    def load_filter_list(self) -> tuple[list, list]:
        """Load whitelist and blacklist IP lists from files. Supports both single IPs and CIDR ranges."""

        def load_ip_list(
            file_path: str | Path, current_hash: str, hash_attribute: str, list_attribute: str
        ) -> list:
            new_hash = self.calculate_file_hash(file_path)
            if new_hash != current_hash:
                ip_list = []
                if os.path.exists(file_path):
                    with open(file_path, "r") as f:
                        for line in f:
                            ip = line.strip()
                            if ip and not ip.startswith("#"):  # Skip comments
                                try:
                                    # Try as single IP first
                                    ip_list.append(ipaddress.ip_address(ip))
                                except ValueError:
                                    try:
                                        # Try as CIDR network
                                        ip_list.append(ipaddress.ip_network(ip, strict=False))
                                    except ValueError:
                                        # Invalid IP format, skip
                                        continue
                setattr(self, hash_attribute, new_hash)
                setattr(self, list_attribute, ip_list)
                return ip_list
            else:
                # Hash unchanged, return cached list
                return getattr(self, list_attribute)

        self.whitelist = load_ip_list(
            self.whitelist_file, self._whitelist_hash, "_whitelist_hash", "whitelist"
        )
        self.blacklist = load_ip_list(
            self.blacklist_file, self._blacklist_hash, "_blacklist_hash", "blacklist"
        )

        return self.whitelist, self.blacklist

    def is_allowed(self, ip: str) -> bool:
        """
        Checks if the given IP address is allowed based on the whitelist and blacklist.
        - If the whitelist is not empty, the IP must be in the whitelist to be allowed.
        - If the whitelist is empty, the IP is denied if it is in the blacklist.
        - If the whitelist is empty and IP is not in the blacklist, it is allowed.
        Supports both single IPs and CIDR ranges.
        """
        self.load_filter_list()

        try:
            ip_addr = ipaddress.ip_address(ip)
        except ValueError:
            return False

        # Check whitelist (if not empty, IP must be whitelisted)
        if self.whitelist:
            for entry in self.whitelist:
                if isinstance(entry, (ipaddress.IPv4Network, ipaddress.IPv6Network)):
                    # CIDR range check
                    if ip_addr in entry:
                        return True
                else:
                    # Single IP check
                    if ip_addr == entry:
                        return True
            return False

        # Check blacklist (if whitelist is empty)
        for entry in self.blacklist:
            if isinstance(entry, (ipaddress.IPv4Network, ipaddress.IPv6Network)):
                # CIDR range check
                if ip_addr in entry:
                    return False
            else:
                # Single IP check
                if ip_addr == entry:
                    return False

        return True

    def add_to_blacklist(self, ip: str) -> None:
        """Add a given IP to the blacklist file."""
        try:
            ip_obj = ipaddress.ip_address(ip)
        except ValueError:
            return
        
        # Check if already in blacklist
        ip_str = str(ip_obj)
        for entry in self.blacklist:
            if str(entry) == ip_str:
                return  # Already in blacklist
        
        # Add to in-memory list
        self.blacklist.append(ip_obj)
        
        # Append to file
        try:
            # Check if file exists and has content
            file_exists = os.path.exists(self.blacklist_file)
            needs_newline = False
            
            if file_exists:
                with open(self.blacklist_file, "r") as f:
                    content = f.read()
                    if content and not content.endswith("\n"):
                        needs_newline = True
            
            with open(self.blacklist_file, "a") as file:
                if needs_newline:
                    file.write("\n")
                file.write(ip_str + "\n")
            
            # Update hash after writing
            self._blacklist_hash = self.calculate_file_hash(self.blacklist_file)
        except Exception as e:
            # Log error but don't fail - in-memory list is updated
            print(f"[Usgromana] Warning: Failed to write IP to blacklist file: {e}")

    def create_ip_filter_middleware(self) -> web.middleware:
        """Create the middleware for managing blacklisted and whitelisted ip."""

        @web.middleware
        async def ip_filter_middleware(request: web.Request, handler) -> web.Response:
            ip = get_ip(request)

            if not self.is_allowed(ip):
                return await handle_access_denied(
                    request,
                    "Access denied: IP is either not whitelisted or is blacklisted.",
                )

            return await handler(request)

        async def handle_access_denied(
            request: web.Request, message: str
        ) -> web.Response:
            """Handle denied access cases."""
            accept_header = request.headers.get("Accept", "")
            if "text/html" in accept_header:
                return web.HTTPForbidden(reason=message)
            else:
                return web.json_response({"error": message}, status=403)

        return ip_filter_middleware
