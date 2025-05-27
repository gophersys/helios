import grpc
from corekinect.utils import Logger
from src.shared.types import *

class FirmwareHandler:
    def __init__(self, logger: Logger):
        self.logger = logger

    def list_programmers(self, request: Empty, context: grpc.ServicerContext) -> ListProgrammersResponse:
        """List available programmers."""
        self.logger.info("ListProgrammers request received")
        return ListProgrammersResponse(
            success=False,
            message="Not implemented",
            programmers=[]
        )

    def list_fw_files(self, request: Empty, context: grpc.ServicerContext) -> ListFwFilesResponse:
        """List available firmware files."""
        self.logger.info("ListFwFiles request received")
        return ListFwFilesResponse(files=[])

    def upload_fw_file(self, request: UploadFwFileRequest, context: grpc.ServicerContext) -> UploadFwFileResponse:
        """Upload a firmware file."""
        self.logger.info(f"UploadFwFile request received for {request.name}")
        return UploadFwFileResponse(
            success=False,
            message="Not implemented",
            sha256_digest=""
        )

    def delete_fw_file(self, request: DeleteFwFileRequest, context: grpc.ServicerContext) -> DeleteFwFileResponse:
        """Delete a firmware file."""
        self.logger.info(f"DeleteFwFile request received for {request.file_info.name}")
        return DeleteFwFileResponse(success=False, message="Not implemented")

    def flash_fw_file(self, request: FlashFwFileRequest, context: grpc.ServicerContext) -> FlashFwFileResponse:
        """Flash a firmware file."""
        self.logger.info(f"FlashFwFile request received for {request.file_info.name}")
        return FlashFwFileResponse(
            success=False,
            message="Not implemented",
            time_ms=0
        ) 