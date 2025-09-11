"""
SSH Tunnel utility for database connections
"""
import logging
import threading
import time
from typing import Optional
from sshtunnel import SSHTunnelForwarder
import paramiko

from ..core.config import settings

logger = logging.getLogger(__name__)


class SSHTunnelManager:
    """Manages SSH tunnel for database connections"""
    
    def __init__(self):
        self.tunnel: Optional[SSHTunnelForwarder] = None
        self.is_connected = False
        self._lock = threading.Lock()
    
    def start_tunnel(self) -> bool:
        """Start SSH tunnel if configured"""
        if not settings.use_ssh_tunnel:
            logger.info("SSH tunnel disabled")
            return True
        
        if self.is_connected:
            logger.info("SSH tunnel already connected")
            return True
        
        with self._lock:
            try:
                logger.info(f"Starting SSH tunnel to {settings.ssh_host}:{settings.ssh_port}")
                
                # Prepare SSH connection arguments
                ssh_args = {
                    'ssh_address_or_host': settings.ssh_host,
                    'ssh_port': settings.ssh_port,
                    'ssh_username': settings.ssh_username,
                    'remote_bind_address': (settings.ssh_remote_host, settings.ssh_remote_port),
                    'local_bind_address': ('127.0.0.1', settings.ssh_local_port),
                    'allow_agent': False,
                    'host_pkey_directories': []
                }
                
                # Add authentication method
                if settings.ssh_key_path:
                    logger.info(f"Using SSH key: {settings.ssh_key_path}")
                    ssh_args['ssh_pkey'] = settings.ssh_key_path
                elif settings.ssh_password:
                    logger.info("Using SSH password authentication")
                    ssh_args['ssh_password'] = settings.ssh_password
                else:
                    raise ValueError("Either ssh_key_path or ssh_password must be provided")
                
                # Create tunnel
                self.tunnel = SSHTunnelForwarder(**ssh_args)
                
                # Start tunnel
                self.tunnel.start()
                
                # Wait for tunnel to be ready
                max_attempts = 10
                for attempt in range(max_attempts):
                    if self.tunnel.is_active:
                        break
                    time.sleep(1)
                    logger.info(f"Waiting for SSH tunnel... attempt {attempt + 1}/{max_attempts}")
                
                if not self.tunnel.is_active:
                    raise ConnectionError("SSH tunnel failed to start")
                
                self.is_connected = True
                local_port = self.tunnel.local_bind_port
                logger.info(f"SSH tunnel established: localhost:{local_port} -> {settings.ssh_remote_host}:{settings.ssh_remote_port}")
                
                return True
                
            except Exception as e:
                logger.error(f"Failed to start SSH tunnel: {e}")
                if self.tunnel:
                    try:
                        self.tunnel.stop()
                    except:
                        pass
                    self.tunnel = None
                self.is_connected = False
                return False
    
    def stop_tunnel(self):
        """Stop SSH tunnel"""
        with self._lock:
            if self.tunnel and self.is_connected:
                try:
                    logger.info("Stopping SSH tunnel")
                    self.tunnel.stop()
                    self.is_connected = False
                    logger.info("SSH tunnel stopped")
                except Exception as e:
                    logger.error(f"Error stopping SSH tunnel: {e}")
                finally:
                    self.tunnel = None
    
    def get_local_port(self) -> Optional[int]:
        """Get the local port of the SSH tunnel"""
        if self.tunnel and self.is_connected:
            return self.tunnel.local_bind_port
        return None
    
    def is_tunnel_active(self) -> bool:
        """Check if tunnel is active"""
        return self.is_connected and self.tunnel and self.tunnel.is_active
    
    def restart_tunnel(self) -> bool:
        """Restart SSH tunnel"""
        logger.info("Restarting SSH tunnel")
        self.stop_tunnel()
        time.sleep(2)  # Wait a bit before restarting
        return self.start_tunnel()


# Global tunnel instance
_tunnel_manager = SSHTunnelManager()


def get_tunnel_manager() -> SSHTunnelManager:
    """Get global tunnel manager instance"""
    return _tunnel_manager


def ensure_tunnel_active() -> bool:
    """Ensure SSH tunnel is active if configured"""
    if not settings.use_ssh_tunnel:
        return True
    
    tunnel_mgr = get_tunnel_manager()
    
    if not tunnel_mgr.is_tunnel_active():
        logger.warning("SSH tunnel is not active, attempting to start")
        return tunnel_mgr.start_tunnel()
    
    return True


def get_database_url_with_tunnel() -> str:
    """Get database URL modified for SSH tunnel if applicable"""
    if not settings.use_ssh_tunnel:
        return settings.database_url
    
    tunnel_mgr = get_tunnel_manager()
    
    if not tunnel_mgr.is_tunnel_active():
        raise ConnectionError("SSH tunnel is not active")
    
    # Replace the host and port in the database URL with localhost and tunnel port
    import re
    from urllib.parse import urlparse, urlunparse
    
    parsed = urlparse(settings.database_url)
    
    # Get the actual local port from the tunnel
    local_port = tunnel_mgr.get_local_port()
    if not local_port:
        local_port = settings.ssh_local_port
    
    # Replace netloc (host:port part)
    new_netloc = f"{parsed.username}:{parsed.password}@localhost:{local_port}" if parsed.password else f"{parsed.username}@localhost:{local_port}"
    
    # Reconstruct URL
    new_parsed = parsed._replace(netloc=new_netloc)
    tunnel_url = urlunparse(new_parsed)
    
    logger.info(f"Using tunneled database URL: {tunnel_url.replace(parsed.password or '', '***')}")
    return tunnel_url
