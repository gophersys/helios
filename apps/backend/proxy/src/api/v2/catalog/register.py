from flask import Flask

from .platforms.register import platforms_register
from .hosts.register import hosts_register
from .socket_servers.register import socket_servers_register


def catalog_register(api: Flask):
    # Subgroups
    platforms_register(api)
    hosts_register(api)
    socket_servers_register(api)
