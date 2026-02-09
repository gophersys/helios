# Standard includes
from typing import Dict, List, Optional

# Corekinect libraries
from corekinect.mtib_client.v2 import MtibV2Client
from corekinect.mtib_client.v2.client.shell import ShellCommandHelper
from corekinect.mtib_client.v2.client.cmd_comms import CommsShellCommands
from corekinect.mtib_client.v2.client.cmd_alpha_app import AlphaAppShellCommands


class PostTestSharedData:
    def __init__(self):
        self.client: Optional[MtibV2Client] = None
        self.app_shell: Optional[ShellCommandHelper] = None
        self.comms_shell: Optional[ShellCommandHelper] = None
        self.app_cmds: Optional[AlphaAppShellCommands] = None
        self.comms_cmds: Optional[CommsShellCommands] = None
        self.imei: Optional[str] = None
        self.iccids: Optional[List[str]] = None


# Singleton global object for shared data
post_test_shared_data: Dict[str, PostTestSharedData] = {}
